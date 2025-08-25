import { ref, reactive } from 'vue';
import axios from 'axios';
import { startOfWeek, endOfWeek } from 'date-fns';

const apiUrl = `http://${import.meta.env.VITE_FLASK_HOST}:${import.meta.env.VITE_FLASK_PORT}`;

const machines = ref([]);
//const exec_plans = ref([]);
const new_exec_plans = ref([]);
const production_orders = ref([]);

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
          day: 'dd/MM/yyyy', // Format for x-axis ticks
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
        offset: true, // Align bars with the middle of the categories
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
            `Reels: ${quantity / orderInc}`
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

const generateDistinctColor = (index) => {
  // Use golden ratio for better distribution
  const goldenRatioConjugate = 0.618033988749895;

  // Start with a random hue and use golden ratio to get distinct colors
  let hue = (index * goldenRatioConjugate) % 1;
  hue = Math.floor(hue * 360);
  
  // Set minimum saturation and constrained lightness range
  // These ranges ensure colors are never too dark (black) or too light (white)
  let saturation = 70 + (index % 4) * 7; // Range: 70-91%
  let lightness = 50 + (index % 5) * 5;  // Range: 50-70%
  
  // Force additional constraints to be absolutely sure
  if (lightness < 40) lightness = 40; // Ensure never too dark
  if (lightness > 75) lightness = 75; // Ensure never too light
  if (saturation < 50) saturation = 50; // Ensure enough color saturation

  return `hsl(${hue}, ${saturation}%, ${lightness}%)`;
};

const generateBorderColor = (color) => {
  if (!color || typeof color !== 'string') {
    return '#666666';
  }
  
  // Updated regex to properly match the HSL pattern with or without commas
  const hslMatch = color.match(/hsl\((\d+),?\s*(\d+)%,?\s*(\d+)%\)/);
  if (hslMatch) {
    const [_, h, s, l] = hslMatch;
    
    // Ensure darker border but not too dark
    const newLightness = Math.max(30, Math.min(Number(l) - 15, 60));
    
    return `hsl(${h}, ${s}%, ${newLightness}%)`;
  }
  
  return color;
};

export const getData = async (planoId) => {
  const path = `${apiUrl}/getNewChartData`;
  try {
    const res = await axios.get(path, {
      params: { planoId },
      headers: { 'Content-Type': 'application/json' },
      withCredentials: true
    });
    //exec_plans.value = res.data.exec_plans;
    new_exec_plans.value = res.data.new_exec_plans;
    machines.value = res.data.machines;
    production_orders.value = res.data.production_orders;

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
    options.scales.y.labels = machines.value.map((machine, _) => machine.name);

    data.datasets.splice(0, data.datasets.length); // Clear existing data

    // Create a better item to color mapping
    const uniqueItems = [...new Set(new_exec_plans.value.map(plan => plan.itemRelated))];
    const colorMap = new Map();

    // Pre-generate colors for all unique items
    uniqueItems.forEach((item, index) => {
      colorMap.set(item, generateDistinctColor(index));
    });

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

    /*exec_plans.value.forEach((plan) => {
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

      // Override the color to a greyish shade
      const greyColor = "#B0BEC5"; // Light grey (you can adjust this)
      const greyBorderColor = "#78909C"; // Darker grey for the border

      dt.backgroundColor.push(greyColor);
      dt.borderColor.push(greyBorderColor);
    });*/

    production_orders.value.forEach((plan) => {
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
        name: plan.item,
        quantity: plan.quantity,
        orderInc: plan.orderIncrement,
      };
      dt.data.push(data);
    
      // Override the color to a greyish shade
      const greyColor = "#B0BEC5"; // Light grey (you can adjust this)
      const greyBorderColor = "#78909C"; // Darker grey for the border

      dt.backgroundColor.push(greyColor);
      dt.borderColor.push(greyBorderColor);
    });

    new_exec_plans.value.forEach((plan) => {
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

      const color = colorMap.get(plan.itemRelated) || generateDistinctColor(dt.data.length);
      dt.backgroundColor.push(color);
      dt.borderColor.push(generateBorderColor(color));
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
