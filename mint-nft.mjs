import { Lucid, Blockfrost, fromHex, toHex } from "lucid-cardano";

const lucid = await Lucid.new(
  new Blockfrost(
    "https://cardano-preprod.blockfrost.io/api/v0",
    "preprod5esmnsvZxjqhrRltlDVtsHPQRtArki34"
  ),
  "Preprod"
);

// あなたの秘密鍵をインポート
const privateKey =
  "ed25519_sk12mqakynx7vxwz558mlu3vg7000wzh8dwznndthc2qdsraz60l4hqr2zn6k";

lucid.selectWalletFromPrivateKey(privateKey);

// NFT用の情報を準備
const policyId = lucid.utils.mintingPolicyToId(
  lucid.utils.nativeScriptFromJson({
    keyHash: "90a4b47b94e37bcb53c9e09cb500430d1b59053076f63c46b99fe728",
    type: "sig",
  })
);
const assetName = "MyTestNFT";
const unit = policyId + toHex(assetName);
const metadata = {
  [policyId]: {
    [assetName]: {
      name: "My Test NFT",
      image: "ipfs://QmbE24FNETgqX7EhwkJCZGRUWQzkazsHxtYPHf1GGoqJu6",
      mediaType: "image/gif",
      description: "This is a test NFT with a GIF image.",
    },
  },
};

// トランザクション構築
const tx = await lucid
  .newTx()
  .attachMintingPolicy(
    lucid.utils.nativeScriptFromJson({
      type: "sig",
      keyHash: "90a4b47b94e37bcb53c9e09cb500430d1b59053076f63c46b99fe728",
    })
  )
  .mintAssets({ [unit]: 1n })
  .attachMetadata(721, metadata)
  .payToAddress(
    "addr_test1vzg2fdrmjn3hhj6ne8sfedgqgvx3kkg9xpm0v0zxhx07w2qg2hmyd",
    { [unit]: 1n }
  )
  .complete();

const signedTx = await tx.sign().complete();
const txHash = await signedTx.submit();

console.log("? Minted! Tx Hash:", txHash);
