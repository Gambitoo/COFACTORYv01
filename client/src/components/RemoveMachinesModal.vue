<template>
    <div class="modal-backdrop">
        <div class="modal-content">
            <!-- Machine List -->
            <h2>Remover Máquinas</h2>
            <div class="checkbox-group">
                <div class="scroll-container">
                    <label v-for="(machine, index) in machines" :key="index">
                        <input type="checkbox" :value="machine" v-model="selectedMachines" />
                        {{ machine }}
                    </label>
                </div>
            </div>
            <div class="modal-actions">
                <button @click="confirm">Confirmar</button>
                <button @click="close">Cancelar</button>
            </div>
        </div>
    </div>
</template>


<script>
export default {
    props: {
        machines: Array,
    },
    data() {
        return {
            selectedMachines: [],
        };
    },
    methods: {
        confirm() {
            this.$emit("confirm", this.selectedMachines);
        },
        close() {
            this.$emit("close");
        },
    },
};
</script>

<style scoped>
.modal-backdrop {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background-color: rgba(0, 0, 0, 0.5);
    display: flex;
    justify-content: center;
    align-items: center;
    z-index: 1000;
}

.modal-content {
    background: white;
    padding: 20px;
    border-radius: 8px;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    width: 400px;
    text-align: center;
}

.checkbox-group {
    margin: 10px 0;
    display: flex;
    flex-direction: column;
    align-items: flex-start;
}

.scroll-container {
    max-height: 350px;
    overflow-y: auto;
    width: 100%;
    padding: 5px;
    border: 1px solid #ccc;
    border-radius: 4px;
}

.checkbox-group label {
    display: block;
    cursor: pointer;
}

.modal-actions {
    display: flex;
    justify-content: space-between;
    margin-top: 15px;
}

.modal-actions button {
    margin: 5px;
    padding: 8px 15px;
    border: none;
    border-radius: 5px;
    cursor: pointer;
}

.modal-actions button:first-child {
    background-color: #4CAF50;
    color: white;
}

.modal-actions button:first-child:hover {
    background-color: #45a049;
}

.modal-actions button:last-child {
    background-color: #f44336;
    color: white;
}

.modal-actions button:last-child:hover {
    background-color: #d32f2f;
}
</style>
