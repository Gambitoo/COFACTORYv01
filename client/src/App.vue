<template>
  <div v-html="htmlHeader"></div>
  <RouterView />
  <div v-html="htmlFooter"></div>
</template>
   
  <script setup>
  import { RouterView } from 'vue-router'
  import { ref, onMounted } from 'vue'
   
  const htmlHeader = ref('')
  const htmlFooter = ref('')
   
  const fetchHtml = async () => {
    try {
          const response = await fetch('/API/Menu')
          if (!response.ok) throw new Error('Erro ao buscar HTML')
          htmlHeader.value = await response.text()
          } catch (error) {
                  console.error(error)
                  htmlHeader.value = 'Erro ao carregar conteúdo.'
          }
   
          try {
          const response = await fetch('/API/Footer')
          if (!response.ok) throw new Error('Erro ao buscar HTML')
          htmlFooter.value = await response.text()
          } catch (error) {
                  console.error(error)
                  htmlFooter.value = 'Erro ao carregar conteúdo.'
          }
  }
   
  onMounted(fetchHtml)
</script>