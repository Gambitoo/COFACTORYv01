<template>
    <div class="branch-modal">
        <h2>Escolha a Unidade de Produção:</h2>
        <button @click="$emit('confirm', 'COFACTORY_PT')">COFACTORY PT</button>
        <button @click="$emit('confirm', 'COFACTORY_GR')">COFACTORY GR</button>
    </div>
</template>

<script>
export default {
    name: "BranchSelectionModal",
};
</script>

<style scoped>
.branch-modal {
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    background: white;
    padding: 20px;
    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
    text-align: center;
}
button {
    margin: 10px;
    padding: 10px 20px;
    font-size: 16px;
    cursor: pointer;
    background-color: #4CAF50;
    color: white;
    border: none;
    border-radius: 5px;
}
button:hover {
    background-color: #45a049;
}
</style>
