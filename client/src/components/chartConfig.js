import { ref, reactive } from 'vue';
import axios from 'axios';
import { startOfWeek, endOfWeek } from 'date-fns';

export const machines = ref([]);
const exec_plans = ref([]);
const time_units = ref([]);
export const data = reactive({
  datasets: [],
});

export const options = reactive({
  responsive: true,
  maintainAspectRatio: false, // Allow flexible height
  layout: {
    padding: {
      left: 100,
      right: 100,
    },
  },
  
  indexAxis: 'y',
  scales: {
    x: {
      position: 'top',
      type: 'time',
      time: {
        unit: 'day',
        displayFormats: {
          day: 'dd/MM/yyyy', 
        },
        stepSize: 1,
      },
      min: '',
      max: '',
      ticks: {
        font: {
          weight: 'bold',
        }
      },
    },
    y: {
      type: 'category',
      grid: {
        offset: true,
      },
      ticks: {
        font: {
          weight: 'bold',
        }
      },
    },
  },
  plugins: {
    legend: {
      display: false,
    },
    tooltip: {
      yAlign: 'bottom',
      callbacks: {
        label: function (context) {
          const startTime = context.raw?.x[0]; 
          const endTime = context.raw?.x[1];   
          const itemRelated = context.raw?.name; 
          const itemRoot = context.raw?.root;
          const quantity = context.raw?.quantity;
          const orderInc = context.raw?.orderInc;
    
          // Format the tooltip string
          return [
            `Root: ${itemRoot}`,
            `Item: ${itemRelated}`,
            `Start Time: ${new Date(startTime).toLocaleString()}`,
            `End Time: ${new Date(endTime).toLocaleString()}`,
            `Quantity: ${quantity}`,
            `Reels: ${quantity/orderInc}`
          ];
        },
      },
    },
    zoom: {
      zoom: {
        drag: {
          enabled: true,
          backgroundColor: 'rgba(48, 47, 47, 0.25)',
        },
        
      }
    },
  },
});

const generateColor = (index, isBorder = false) => {
  // Gera cores com base no índice variando a tonalidade (hue) no espectro HSL
  const hue = (index * 137.508) % 360; // Número de ouro para distribuição uniforme
  const saturation = 70; // Saturação fixa para manter cores vibrantes
  const lightness = isBorder ? 40 : 60; // Diferença entre borda e preenchimento
  return `hsl(${hue}, ${saturation}%, ${lightness}%)`;
};

// Utility function to darken/lighten colors
const shadeColor = (color, percent) => {
  let num = parseInt(color.slice(1), 16),
    amt = Math.round(2.55 * percent),
    R = (num >> 16) + amt,
    G = ((num >> 8) & 0x00ff) + amt,
    B = (num & 0x0000ff) + amt;
  return (
    '#' +
    (0x1000000 + (R < 255 ? (R < 1 ? 0 : R) : 255) * 0x10000 +
      (G < 255 ? (G < 1 ? 0 : G) : 255) * 0x100 +
      (B < 255 ? (B < 1 ? 0 : B) : 255))
      .toString(16)
      .slice(1)
  );
};

export const getData = async () => {
  console.log('GanttChart getData()');
  const path = 'http://localhost:5001/getChartData';
  try {
    const res = await axios.get(path);
    exec_plans.value = res.data.exec_plans;
    machines.value = res.data.machines;

    machines.value.sort((a, b) => {
      const getTypeOrder = (type) => {
        if (type.startsWith("ROD")) return 1;
        if (type.startsWith("MDW")) return 2;
        if (type.startsWith("BUN")) return 3;
        return 4;
      };

      const typeOrderA = getTypeOrder(a.name);
      const typeOrderB = getTypeOrder(b.name);

      if (typeOrderA !== typeOrderB) {
        return typeOrderA - typeOrderB; 
      }

      // If machines are the same, sort numerically
      const numA = parseInt(a.name.match(/\d+/)[0]);
      const numB = parseInt(b.name.match(/\d+/)[0]);
      return numA - numB;
    });

    // Ensure the y-axis labels match the machine names
    options.scales.y.labels = machines.value.map((machine, i) => machine.name);

    data.datasets.splice(0, data.datasets.length); // Clear existing data

    const colorMap = new Map(); 
    let colorIndex = 0; // Track the current color index

    let dt = {
      label: "Plano",
      fill: false,
      data: [],
      backgroundColor: [], 
      borderColor: [], 
      barPercentage: 0.8,
    };

    let minST = Infinity; // Track the earliest start time
    let maxCoT = -Infinity; // Track the latest completion time

    exec_plans.value.forEach((plan) => {
      const startTime = new Date(plan.ST).getTime();
      const completionTime = new Date(plan.CoT).getTime();

      // Update min and max
      if (startTime < minST) minST = startTime;
      if (completionTime > maxCoT) maxCoT = completionTime;

      let data = {
        x: [
          new Date(plan.ST).toISOString(), // Ensure valid ISO string
          new Date(plan.CoT).toISOString(),
        ],
        y: plan.machine,
        name: plan.itemRelated,
        root: plan.itemRoot,
        quantity: plan.quantity,
        orderInc: plan.orderIncrement,
      };
      dt.data.push(data);

      // Set up the colors for each bar
      if (!colorMap.has(plan.itemRelated)) {
        colorMap.set(plan.itemRelated, generateColor(colorIndex++));
      }
      const color = colorMap.get(plan.itemRelated);

      dt.backgroundColor.push(color); // Use the mapped color
      dt.borderColor.push(shadeColor(color, -20)); // Use a darker shade for the border
    });
    data.datasets.push(dt);

    // Get current date and calculate the start and end of the current week
    const currentDate = new Date();
    const minDate = startOfWeek(currentDate, { weekStartsOn: 1 }); // Monday as the first day of the week
    const maxDate = endOfWeek(currentDate, { weekStartsOn: 1 }); // Sunday as the last day of the week

    // Update x-axis dynamically to show the current week
    options.scales.x.min = minDate.toISOString();
    options.scales.x.max = maxDate.toISOString();
  } catch (error) {
    console.error('Error fetching data:', error);
  }
};
