const express = require("express");
const path = require("path");
 
const app = express();
 
// Servir arquivos estáticos da pasta 'dist'
app.use("/App/MetalPlanning", express.static(path.join(__dirname, "dist")));
 
// Redirecionar todas as rotas para o index.html
app.get("/App/MetalPlanning/*", (req, res) => {
  res.sendFile(path.join(__dirname, "dist", "index.html"));
});
 
const PORT = 5173;  // Ou a porta que você deseja
app.listen(PORT, () => {
  console.log(`Servidor rodando na porta ${PORT}`);
});