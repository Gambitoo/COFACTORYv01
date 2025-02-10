<template>
  <div>
    <!-- Navigation buttons -->
    <div
      style="text-align: right; margin-right: 10px; display: flex; justify-content: flex-end; align-items: center; position: relative;">
      <!-- Previous and Next Week Buttons -->
      <button @click="previousWeek" :class="{ 'animate-click': isAnimating === 'previousWeek' }"
        @animationend="resetAnimation" aria-label="Previous Week">
        <font-awesome-icon icon="arrow-left" />
      </button>
      <button @click="nextWeek" :class="{ 'animate-click': isAnimating === 'nextWeek' }" @animationend="resetAnimation"
        aria-label="Next Week">
        <font-awesome-icon icon="arrow-right" />
      </button>
      <button @click="toggleFilters" :class="{ 'animate-click': isAnimating === 'toggleFilters' }"
        @animationend="resetAnimation" aria-label="Filters">
        <font-awesome-icon icon="filter" />
      </button>

      <!-- Filters Dropdown Menu -->
      <transition name="fade">
        <div v-if="showFilters" style="
              position: absolute;
              top: 40px;
              right: 10px;
              background: white;
              box-shadow: 0px 4px 6px rgba(0, 0, 0, 0.1);
              border: 1px solid #ddd;
              border-radius: 5px;
              padding: 10px;
              z-index: 1000;
            ">
          <!-- Additional Filters -->
          <div style="margin-bottom: 10px;">
            <label style="font-weight: bold;">Filtrar por Processo</label>
            <div v-if="hasRODMachines">
              <label>
                <input type="checkbox" value="ROD" v-model="selectedMachineTypes" />
                ROD
              </label>
            </div>
            <div>
              <label>
                <input type="checkbox" value="MDW" v-model="selectedMachineTypes" />
                MDW
              </label>
            </div>
            <div>
              <label>
                <input type="checkbox" value="BUN" v-model="selectedMachineTypes" />
                BUN
              </label>
            </div>
          </div>
        </div>
      </transition>
    </div>

    <!-- Gantt Chart -->
    <div :style="{ height: chartHeight + 'px', overflowY: 'auto' }" @dblclick="resetZoom">
      <Bar v-if="isDataLoaded" ref="ganttChart" :data="data" :options="options" />
      <p v-else>A carregar dados...</p>
    </div>
  </div>
</template>

<script lang="ts">
import { Bar } from 'vue-chartjs';
import * as resultsChartConfig from './resultsChartConfig.js';
import { FontAwesomeIcon } from '@fortawesome/vue-fontawesome';

import {
  Chart as ChartJS,
  Title,
  Tooltip,
  Legend,
  BarElement,
  CategoryScale,
  LinearScale,
  TimeScale,
} from 'chart.js';
import 'chartjs-adapter-date-fns'; // Required for time scale to work properly
import zoomPlugin from 'chartjs-plugin-zoom';
import { startOfWeek, endOfWeek, addWeeks, subWeeks } from 'date-fns'; // Import week navigation functions

ChartJS.register(Title, Tooltip, Legend, BarElement, CategoryScale, LinearScale, TimeScale, zoomPlugin);

export default {
  components: { Bar, FontAwesomeIcon },
  data() {
    return {
      originalData: null as any,
      originalOptions: null as any,
      data: resultsChartConfig.data,
      options: resultsChartConfig.options,
      isDataLoaded: false, // Track loading state
      chartHeight: null as any,
      baseHeight: null as any,
      padding: null as any,
      currentWeekRange: {
        start: null as Date | null,
        end: null as Date | null,
      },
      showFilters: false,
      selectedMachineTypes: ['ROD', 'MDW', 'BUN'],
      isAnimating: null as any, // Tracks which button is being animated
    };
  },
  computed: {
    // Check if there are machines that start with "ROD"
    hasRODMachines() {
      return this.originalOptions.scales.y.labels.some((label) => label && label.startsWith('ROD'));
    }
  },
  methods: {
    async fetchData() {
      await resultsChartConfig.getData();
      this.isDataLoaded = true;

      // Dynamically adjust chart height
      this.baseHeight = 40; // Height per machine
      this.padding = 100; // Extra padding
      this.chartHeight = resultsChartConfig.machines.value.length * this.baseHeight + this.padding;

      // Initialize week range
      const today = new Date();
      this.setWeekRange(today);
    },
    toggleFilters() {
      this.triggerButtonAnimation('toggleFilters');
      this.showFilters = !this.showFilters; // Toggle dropdown menu visibility
    },
    setWeekRange(date: Date) {
      const startOfWeekDate = startOfWeek(date, { weekStartsOn: 1 }); // Week starts on Monday
      const endOfWeekDate = endOfWeek(date, { weekStartsOn: 1 }); // Week ends on Sunday

      this.currentWeekRange.start = startOfWeekDate;
      this.currentWeekRange.end = endOfWeekDate;

      // Update chart options with the new date range
      this.options = {
        ...this.options,
        scales: {
          ...this.options.scales,
          x: {
            ...this.options.scales.x,
            min: startOfWeekDate.toISOString(),
            max: endOfWeekDate.toISOString(),
          },
        },
      };

      // Force a re-render by updating `data` in a shallow manner
      this.data = { ...this.data };
    },
    previousWeek() {
      this.triggerButtonAnimation('previousWeek');
      if (this.currentWeekRange.start) {
        const newStartDate = subWeeks(this.currentWeekRange.start, 1);
        this.setWeekRange(newStartDate);
      }
    },
    nextWeek() {
      this.triggerButtonAnimation('nextWeek');
      if (this.currentWeekRange.start) {
        const newStartDate = addWeeks(this.currentWeekRange.start, 1);
        this.setWeekRange(newStartDate);
      }
    },
    filterbyMachine() {
      // Ensure selectedMachineTypes are sorted by the desired order
      this.selectedMachineTypes = this.selectedMachineTypes.sort((a, b) => {
        const order = ['ROD', 'MDW', 'BUN'];
        return order.indexOf(a) - order.indexOf(b);
      });

      console.log(this.originalData.datasets[0].data);

      // Filter datasets based on selected machine types
      const filteredDatasets = this.originalData.datasets[0].data.filter((dataset) =>
        this.selectedMachineTypes.some((filter) => dataset.y.startsWith(filter))
      );

      // Filter y-axis labels based on selected machine types
      const filteredMachines = this.originalOptions.scales.y.labels.filter((label) =>
        this.selectedMachineTypes.some((filter) => label.startsWith(filter))
      );

      // Sort the filteredMachines based on the order of selectedMachineTypes
      const sortedFilteredMachines = this.selectedMachineTypes.flatMap((type) =>
        filteredMachines.filter((machine) => machine.startsWith(type))
      );

      this.chartHeight = sortedFilteredMachines.length * this.baseHeight + this.padding;

      const filterColors = [];
      for (let i = 0; i < filteredDatasets.length; i++) {
        const result = this.originalData.datasets[0].data.indexOf(filteredDatasets[i]);
        const colorsResult = this.originalData.datasets[0].backgroundColor[result];
        filterColors.push(colorsResult);
      }

      // Update the chart data and backgroundColors
      this.data = {
        ...this.originalData,
        datasets: [
          {
            ...this.originalData.datasets[0],
            data: filteredDatasets,
            backgroundColor: filterColors,
          },
        ],
      };

      this.options = {
        ...this.options,
        scales: {
          ...this.options.scales,
          y: {
            ...this.options.scales.y,
            labels: sortedFilteredMachines,
          },
        },
      };
    },
    triggerButtonAnimation(buttonName: string) {
      this.isAnimating = buttonName; // Set the button being animated
    },
    resetAnimation() {
      this.isAnimating = null; // Reset the animation state
    },
    resetZoom() {
      // Access the chart instance via the `ref`
      const chartComponent = this.$refs.ganttChart;

      if (chartComponent && chartComponent.chart) {
        chartComponent.chart.resetZoom();
      }
    },
  },
  mounted() {
    this.fetchData().then(() => {
      this.originalData = JSON.parse(JSON.stringify(this.data));
      this.originalOptions = this.options
    });
  },
  watch: {
    selectedMachineTypes: {
      handler() {
        this.filterbyMachine();
      },
      deep: true,
    },
  },
};
</script>

<style scoped>
button {
  background: none;
  cursor: pointer;
  margin: 0 5px;
  margin-bottom: 10px;
  margin-top: 10px;
  border-radius: 5px;
  transition: background-color 0.3s ease, transform 0.2s ease;
}

button:hover {
  background-color: rgba(0, 0, 0, 0.1);
  transform: scale(1.05);
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter,
.fade-leave-to {
  opacity: 0;
}

.animate-click {
  animation: button-click 0.3s ease;
}

@keyframes button-click {
  0% {
    transform: scale(1);
  }

  50% {
    transform: scale(0.9);
  }

  100% {
    transform: scale(1);
  }
}
</style>