const express = require('express');
const app = express();
const port = process.env.PORT || 3000;

app.use(express.json());

app.get('/', (req, res) => {
  res.send('NFT Mint Server is running!');
});

app.post('/mint', async (req, res) => {
  // TODO: Lucid‚ÅMintˆ—i‰¼j
  res.json({ status: 'Mint pretend success!' });
});

app.listen(port, () => {
  console.log(`Server is listening on port ${port}`);
});
