import { generatePrivateKey, getAddressDetails, Lucid } from "lucid-cardano";

const lucid = await Lucid.new(undefined, "Preprod");

// ① 秘密鍵（Base16）
const sk = generatePrivateKey(); // ed25519_sk...
console.log("Private Key:\n", sk);

// ② アドレス（Bech32）
lucid.selectWalletFromPrivateKey(sk);
const addr = await lucid.wallet.address();
console.log("\nBech32 Address:\n", addr);

// ③ Base16アドレス（＝payment credentialのhash部分）
const details = getAddressDetails(addr);
console.log("\nPayment Key Hash (Base16):\n", details.paymentCredential.hash);
