<template>
    <div class="modal-backdrop">
        <div class="modal-content">
            <!-- BoM List -->
            <h2>Remover BOM's</h2>
            <div class="scroll-container">
                <div v-for="(items, rootItem) in BoMs" :key="rootItem" class="bom-group">
                    <h3>{{ rootItem }}</h3>
                    <ul>
                        <li v-for="(itemList, index) in items" :key="index">
                            <label>
                                <input
                                    type="checkbox"
                                    :value="itemList"
                                    :data-root-item="rootItem"
                                    @change="handleSelection(rootItem, itemList, $event)"
                                />
                                {{ itemList.join(", ") }}
                            </label>
                        </li>
                    </ul>
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
            BoMs: Object,
        },
        data() {
            return {
                selectedBoMs: {},
            };
        },
        methods: {
            handleSelection(rootItem, itemList, event) {
                if (event.target.checked) {
                    // Add the checked BoM to itemList
                    if (!this.selectedBoMs[rootItem]) {
                        this.selectedBoMs[rootItem] = [];
                    }
                    this.selectedBoMs[rootItem].push(itemList);
                } else {
                    // Removes the unchecked BoM's from itemList
                    if (this.selectedBoMs[rootItem]) {
                        this.selectedBoMs[rootItem] = this.selectedBoMs[rootItem].filter(
                            (selectedItem) => JSON.stringify(selectedItem) !== JSON.stringify(itemList)
                        );
                        // Remove the root item if no BoM's remain
                        if (this.selectedBoMs[rootItem].length === 0) {
                            delete this.selectedBoMs[rootItem];
                        }
                    }
                }
            },
            confirm() {
                console.log("Selected BoMs to confirm:", this.selectedBoMs);
                this.$emit("confirm", this.selectedBoMs);
            },
            close() {
                console.log("Modal closed. Selected BoMs:", this.selectedBoMs);
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
    width: 600px;
    text-align: left;
}

.scroll-container {
    max-height: 550px;
    overflow-y: auto;
}

.bom-group {
    margin-bottom: 20px;
}

.bom-group h3 {
    margin: 10px 0;
    font-size: 20px;
    color: #333;
}

ul {
    list-style: none; 
    padding: 0;       
    margin: 0;       
}

li {
    margin-bottom: 8px; 
}

.modal-actions {
    display: flex;
    justify-content: space-between;
    margin-top: 20px;
}

.modal-actions button {
    padding: 10px 20px;
    border: none;
    border-radius: 5px;
    cursor: pointer;
    transition: 0.3s;
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
