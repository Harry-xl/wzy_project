const express = require('express');
const cors = require('cors');
const authRouter = require('./auth');
const app = express();

app.use(cors());
app.use(authRouter);

app.listen(3000, () => {
    console.log('Server running on http://localhost:3000');
});
