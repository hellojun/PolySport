import hre from "hardhat";
import fs from "fs";
import path from "path";

// --- Config ---
const BATCH_SIZE = 200;
const BATCH_DELAY_MS = 3000;
const MAX_GAS_PRICE_GWEI = 130;
const GAS_PER_ADDR = 80_000n;
const GAS_OVERHEAD = 50_000n;
const GAS_WAIT_MS = 15_000;
const EOA_CONCURRENCY = 50;

interface AddressEntry {
  address: string;
  tier: string;
}

function loadCSV(filePath: string, tier: string): AddressEntry[] {
  if (!fs.existsSync(filePath)) {
    console.log(`  Skipping ${filePath} (not found)`);
    return [];
  }
  const lines = fs.readFileSync(filePath, "utf-8").trim().split("\n");
  const entries: AddressEntry[] = [];
  for (let i = 1; i < lines.length; i++) {
    const addr = lines[i].split(",")[0].trim().toLowerCase();
    if (addr && hre.ethers.isAddress(addr)) {
      entries.push({ address: hre.ethers.getAddress(addr), tier });
    }
  }
  return entries;
}

function dedup(entries: AddressEntry[]): AddressEntry[] {
  const seen = new Set<string>();
  return entries.filter((e) => {
    const key = e.address.toLowerCase();
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

async function filterEOA(
  provider: any,
  entries: AddressEntry[]
): Promise<{ eoa: AddressEntry[]; contracts: AddressEntry[] }> {
  const eoa: AddressEntry[] = [];
  const contracts: AddressEntry[] = [];

  async function check(entry: AddressEntry): Promise<boolean> {
    for (let attempt = 0; attempt < 3; attempt++) {
      try {
        const code = await provider.getCode(entry.address);
        return code === "0x";
      } catch {
        await new Promise((r) => setTimeout(r, 2000 * (attempt + 1)));
      }
    }
    return true; // assume EOA on failure
  }

  for (let i = 0; i < entries.length; i += EOA_CONCURRENCY) {
    const batch = entries.slice(i, i + EOA_CONCURRENCY);
    const results = await Promise.all(batch.map((e) => check(e)));
    for (let j = 0; j < batch.length; j++) {
      if (results[j]) {
        eoa.push(batch[j]);
      } else {
        contracts.push(batch[j]);
      }
    }
    const done = Math.min(i + EOA_CONCURRENCY, entries.length);
    if (done % 5000 < EOA_CONCURRENCY || done === entries.length) {
      console.log(`  Checked ${done}/${entries.length}...`);
    }
  }
  return { eoa, contracts };
}

async function waitForLowGas(provider: any) {
  while (true) {
    const feeData = await provider.getFeeData();
    const gasPrice = feeData.gasPrice ?? 0n;
    const gasPriceGwei = Number(gasPrice / 1_000_000_000n);
    if (gasPriceGwei <= MAX_GAS_PRICE_GWEI) {
      return gasPrice;
    }
    console.log(
      `  Gas price ${gasPriceGwei} Gwei > ${MAX_GAS_PRICE_GWEI} Gwei limit, waiting ${GAS_WAIT_MS / 1000}s...`
    );
    await new Promise((r) => setTimeout(r, GAS_WAIT_MS));
  }
}

async function findBadAddrs(
  contract: any,
  addrs: string[]
): Promise<Set<string>> {
  const bad = new Set<string>();
  if (addrs.length === 0) return bad;

  // Try the whole batch
  try {
    await contract.batchMint.staticCall(addrs);
    return bad; // all good
  } catch {
    // If single address, it's the bad one
    if (addrs.length === 1) {
      bad.add(addrs[0]);
      return bad;
    }
    // Binary search
    const mid = Math.floor(addrs.length / 2);
    const left = await findBadAddrs(contract, addrs.slice(0, mid));
    const right = await findBadAddrs(contract, addrs.slice(mid));
    for (const a of left) bad.add(a);
    for (const a of right) bad.add(a);
    return bad;
  }
}

async function mintFile(
  csvPath: string,
  tier: string,
  contract: any,
  provider: any,
  startBatch: number = 1
) {
  console.log(`\n=== Processing ${path.basename(csvPath)} (${tier}) ===`);

  const raw = dedup(loadCSV(csvPath, tier));
  if (raw.length === 0) {
    console.log("  No addresses, skipping.");
    return;
  }
  console.log(`  Loaded: ${raw.length} unique addresses`);

  // Filter EOA — reuse cached skip list if available
  const skippedPath = path.resolve(
    __dirname,
    `../skipped_contracts_${tier}.csv`
  );

  let eoa: AddressEntry[];
  if (fs.existsSync(skippedPath)) {
    const skipSet = new Set(
      fs.readFileSync(skippedPath, "utf-8").trim().split("\n").slice(1)
        .map((l) => l.split(",")[0].trim().toLowerCase())
    );
    eoa = raw.filter((e) => !skipSet.has(e.address.toLowerCase()));
    console.log(`  Using cached ${skippedPath} (${skipSet.size} contracts excluded)`);
    console.log(`  EOA: ${eoa.length}`);
  } else {
    console.log("  Filtering non-EOA (first run)...");
    const result = await filterEOA(provider, raw);
    eoa = result.eoa;
    console.log(`  EOA: ${eoa.length}, Skipped (contracts): ${result.contracts.length}`);

    if (result.contracts.length > 0) {
      const csv =
        "wallet_address,user_tier\n" +
        result.contracts.map((e) => `${e.address},${e.tier}`).join("\n") +
        "\n";
      fs.writeFileSync(skippedPath, csv);
      console.log(`  Saved to: ${skippedPath}`);
    }
  }

  if (eoa.length === 0) {
    console.log("  No EOA addresses to mint.");
    return;
  }

  // Batch mint
  const totalBatches = Math.ceil(eoa.length / BATCH_SIZE);
  let minted = 0;
  const failed: AddressEntry[] = [];

  if (startBatch > 1) {
    console.log(`  Skipping to batch ${startBatch}/${totalBatches}\n`);
  }
  console.log(
    `  Starting: ${eoa.length} addresses in ${totalBatches} batches of ${BATCH_SIZE}\n`
  );

  const startIndex = (startBatch - 1) * BATCH_SIZE;

  for (let i = startIndex; i < eoa.length; i += BATCH_SIZE) {
    const batchNum = Math.floor(i / BATCH_SIZE) + 1;
    const batch = eoa.slice(i, i + BATCH_SIZE);
    let addrs = batch.map((e) => e.address);

    console.log(
      `  [${batchNum}/${totalBatches}] Minting ${addrs.length} addresses (${minted}/${eoa.length} done)...`
    );

    try {
      // Dry-run simulation — find and remove bad addresses
      const badAddrs = await findBadAddrs(contract, addrs);
      if (badAddrs.size > 0) {
        console.log(`    ⚠ Removing ${badAddrs.size} bad address(es): ${[...badAddrs].join(", ")}`);
        const goodAddrs = addrs.filter((a) => !badAddrs.has(a));
        // Append bad addresses to skipped file
        const appendLines = [...badAddrs].map((a) => `${a},${tier}`).join("\n") + "\n";
        fs.appendFileSync(skippedPath, appendLines);
        if (goodAddrs.length === 0) {
          console.log(`    Skipping batch (all addresses bad).`);
          minted += 0;
          continue;
        }
        addrs = goodAddrs;
        console.log(`    Proceeding with ${addrs.length} addresses.`);
      }

      const gasPrice = await waitForLowGas(provider);
      const gasLimit = BigInt(addrs.length) * GAS_PER_ADDR + GAS_OVERHEAD;
      const tx = await contract.batchMint(addrs, { gasLimit, gasPrice });
      const receipt = await tx.wait();
      console.log(
        `    ✓ tx: ${receipt.hash}  gas: ${receipt.gasUsed.toString()}`
      );
      minted += addrs.length;
    } catch (err: any) {
      console.error(`    ✗ Batch ${batchNum} failed: ${err.message}`);
      console.error(`    Stopping. Re-run with MINT_FROM=${batchNum} to retry.`);
      failed.push(...batch);
      break;
    }

    if (i + BATCH_SIZE < eoa.length) {
      await new Promise((r) => setTimeout(r, BATCH_DELAY_MS));
    }
  }

  console.log(`  Done! Minted: ${minted}, Failed: ${failed.length}`);

  if (failed.length > 0) {
    const failedPath = path.resolve(
      __dirname,
      `../failed_addresses_${tier}.csv`
    );
    const csv =
      "wallet_address,user_tier\n" +
      failed.map((e) => `${e.address},${e.tier}`).join("\n") +
      "\n";
    fs.writeFileSync(failedPath, csv);
    console.log(`  Failed saved to: ${failedPath}`);
  }
}

async function main() {
  const contractAddress = process.env.CONTRACT_ADDRESS;
  if (!contractAddress) {
    console.error("ERROR: Set CONTRACT_ADDRESS in .env");
    process.exit(1);
  }

  // MINT_TIER: "whale" or "active"; MINT_FROM: start from batch N (1-based)
  const arg = process.env.MINT_TIER || "";
  const startBatch = parseInt(process.env.MINT_FROM || "1", 10) || 1;
  const prdDir = path.resolve(__dirname, "../../prd");
  const provider = hre.ethers.provider;
  const contract = await hre.ethers.getContractAt(
    "PredictionPass",
    contractAddress
  );

  if (arg === "active") {
    await mintFile(
      path.join(prdDir, "polysport_active_addresses.csv"),
      "active",
      contract,
      provider,
      startBatch
    );
  } else if (arg === "whale") {
    await mintFile(
      path.join(prdDir, "polysport_whale_addresses.csv"),
      "whale",
      contract,
      provider,
      startBatch
    );
  } else {
    // Default: whale first, then active
    await mintFile(
      path.join(prdDir, "polysport_whale_addresses.csv"),
      "whale",
      contract,
      provider,
      startBatch
    );
    await mintFile(
      path.join(prdDir, "polysport_active_addresses.csv"),
      "active",
      contract,
      provider,
      startBatch
    );
  }

  const supply = await contract.totalSupply();
  console.log(`\nContract totalSupply: ${supply.toString()}`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
