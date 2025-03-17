<template>
    <div class="modal-backdrop">
        <div class="modal-content">
            <div class="modal-header">
                <h2>{{ title }}</h2>
            </div>
            <div class="checkbox-group">
                <label v-for="(option, index) in criteria" :key="index">
                    <input type="checkbox" :value="index" v-model="selectedCriteria" />
                    {{ option }}
                </label>
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
        title: String,
        criteria: Array,
    },
    data() {
        return {
            visible: true,
            selectedCriteria: [],
        };
    },
    methods: {
        confirm() {
            const newSelectedCriteria = this.criteria.reduce((result, _, index) => {
                result[index] = this.selectedCriteria.includes(index); 
                return result;
            }, {}); 
            this.$emit("confirm", newSelectedCriteria);
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
    width: 300px;
    text-align: center;
}

.modal-header {
    display: flex;
    justify-content: center;
    align-items: center;
    border-bottom: 2px solid #eee;
}

.checkbox-group {
    margin: 10px 0;
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 10px;
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
