import hre from "hardhat";
import fs from "fs";
import path from "path";

// --- Config ---
const BATCH_SIZE = 200;
const BATCH_DELAY_MS = 3000;
const MAX_GAS_PRICE_GWEI = 100;
const GAS_PER_ADDR = 30_000n;
const GAS_OVERHEAD = 50_000n;
const GAS_WAIT_MS = 15_000;

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
  // skip header
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

async function main() {
  const contractAddress = process.env.CONTRACT_ADDRESS;
  if (!contractAddress) {
    console.error("ERROR: Set CONTRACT_ADDRESS in .env");
    process.exit(1);
  }

  const prdDir = path.resolve(__dirname, "../../prd");
  console.log("Loading addresses from prd/ ...");

  // Load whale first, then active (whale gets lower tokenIds)
  const whales = loadCSV(
    path.join(prdDir, "polysport_whale_addresses.csv"),
    "whale"
  );
  const actives = loadCSV(
    path.join(prdDir, "polysport_active_addresses.csv"),
    "active"
  );

  const all = dedup([...whales, ...actives]);
  console.log(
    `  Whale: ${whales.length}, Active: ${actives.length}, Total (deduped): ${all.length}`
  );

  const contract = await hre.ethers.getContractAt(
    "PredictionPass",
    contractAddress
  );
  const provider = hre.ethers.provider;

  const totalBatches = Math.ceil(all.length / BATCH_SIZE);
  let minted = 0;
  const failed: AddressEntry[] = [];

  console.log(
    `\nStarting batch mint: ${all.length} addresses in ${totalBatches} batches of ${BATCH_SIZE}\n`
  );

  for (let i = 0; i < all.length; i += BATCH_SIZE) {
    const batchNum = Math.floor(i / BATCH_SIZE) + 1;
    const batch = all.slice(i, i + BATCH_SIZE);
    const addrs = batch.map((e) => e.address);

    console.log(
      `[${batchNum}/${totalBatches}] Minting ${addrs.length} addresses (${minted}/${all.length} done)...`
    );

    try {
      const gasPrice = await waitForLowGas(provider);
      const gasLimit = BigInt(addrs.length) * GAS_PER_ADDR + GAS_OVERHEAD;

      const tx = await contract.batchMint(addrs, { gasLimit, gasPrice });
      const receipt = await tx.wait();
      console.log(
        `  ✓ tx: ${receipt.hash}  gas used: ${receipt.gasUsed.toString()}`
      );
      minted += addrs.length;
    } catch (err: any) {
      console.error(`  ✗ Batch ${batchNum} failed: ${err.message}`);
      failed.push(...batch);
    }

    if (i + BATCH_SIZE < all.length) {
      await new Promise((r) => setTimeout(r, BATCH_DELAY_MS));
    }
  }

  console.log(`\nDone! Minted: ${minted}, Failed: ${failed.length}`);

  if (failed.length > 0) {
    const failedPath = path.resolve(__dirname, "../failed_addresses.csv");
    const csv =
      "wallet_address,user_tier\n" +
      failed.map((e) => `${e.address},${e.tier}`).join("\n") +
      "\n";
    fs.writeFileSync(failedPath, csv);
    console.log(`Failed addresses saved to: ${failedPath}`);
  }

  const supply = await contract.totalSupply();
  console.log(`Contract totalSupply: ${supply.toString()}`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
