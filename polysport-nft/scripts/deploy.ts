import hre from "hardhat";

async function main() {
  const baseURI = "https://polysport.pro/api/nft/";

  console.log("Deploying PredictionPass...");
  console.log("  baseURI:", baseURI);
  console.log("  network:", hre.network.name);

  const factory = await hre.ethers.getContractFactory("PredictionPass");
  const contract = await factory.deploy(baseURI);
  await contract.waitForDeployment();

  const address = await contract.getAddress();
  console.log("\nPredictionPass deployed to:", address);
  console.log(`https://polygonscan.com/address/${address}`);

  // Wait for block confirmations
  console.log("\nWaiting for 5 block confirmations...");
  const tx = contract.deploymentTransaction();
  if (tx) {
    await tx.wait(5);
    console.log("Confirmed.");
  }

  // Verify on Polygonscan
  if (process.env.POLYGONSCAN_API_KEY) {
    console.log("\nVerifying contract on Polygonscan...");
    try {
      await hre.run("verify:verify", {
        address,
        constructorArguments: [baseURI],
      });
      console.log("Verified!");
    } catch (e: any) {
      if (e.message.includes("Already Verified")) {
        console.log("Already verified.");
      } else {
        console.error("Verification failed:", e.message);
      }
    }
  }

  console.log("\n--- NEXT STEPS ---");
  console.log(`Add to .env:  CONTRACT_ADDRESS=${address}`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
