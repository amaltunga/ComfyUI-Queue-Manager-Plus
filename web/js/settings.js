export const settings =  [
  // Basic settings appear in reverse registration order in ComfyUI.
  {
    id: 'QueueManager.Basic.CleanCachesOnPause',
    name: 'Clean caches on Pause',
    category: ['QUEUE MANAGER PLUS', 'Basic', 'Clean caches on Pause'],
    tooltip: 'Enabled: clears VRAM / RAM when queue is paused',
    type: 'boolean',
    defaultValue: false,
  },
  {
    id: 'QueueManager.Basic.ShowSelectionHints',
    name: 'Show selection mode hints',
    category: ['QUEUE MANAGER PLUS', 'Basic', 'Show selection mode hints'],
    tooltip: 'Show the selection shortcuts and help below the QUEUE MANAGER PLUS tabs.',
    type: 'boolean',
    defaultValue: true,
  },
  {
    id: 'QueueManager.Basic.PageSize',
    name: 'Jobs per page',
    category: ['QUEUE MANAGER PLUS', 'Basic', 'Jobs per page'],
    tooltip: 'Number of jobs to display per page in QUEUE MANAGER PLUS.',
    type: 'number',
    defaultValue: 100,
    attrs: {
      min: 1,
      step: 1,
      max: 200,
    },
  },
  {
    id: 'QueueManager.Basic.StartMode',
    name: 'Run mode on start',
    category: ['QUEUE MANAGER PLUS', 'Basic', 'Run mode on start'],
    tooltip: 'Whether the queue should automatically play or be paused when ComfyUI starts.',
    type: 'combo',
    options: [
      'Play',
      'Pause',
      'Last state',
    ],
    defaultValue: 'Last state',
  },

  // Gallery settings
  {
    id: 'QueueManager.Completed.ListOrder',
    name: 'Completed jobs list order',
    category: ['QUEUE MANAGER PLUS', 'Completed', 'Completed jobs list order'],
    tooltip: 'Order in which completed jobs are displayed in the Completed tab.',
    type: 'combo',
    options: [
      'Newest first',
      'Oldest first',
    ],
    defaultValue: 'Newest first',
  },
  {
    id: 'QueueManager.Completed.GridThumbMode',
    name: 'Grid thumbnail mode',
    category: ['QUEUE MANAGER PLUS', 'Completed', 'Grid thumbnail mode'],
    tooltip: 'How thumbnails are displayed in Grid mode.',
    type: 'combo',
    options: [
      'Square Cropped',
      'Square Fit',
      'As is',
    ],
    defaultValue: 'Square Fit',
  },
  {
    id: 'QueueManager.Completed.CoverThumbMode',
    name: 'Cover thumbnail mode',
    category: ['QUEUE MANAGER PLUS', 'Completed', 'Cover thumbnail mode'],
    tooltip: 'How thumbnails are displayed in Cover mode.',
    type: 'combo',
    options: [
      'Cropped',
      'Fit',
    ],
    defaultValue: 'Cropped',
  },

  // Gallery settings
  {
    id: 'QueueManager.Gallery.AutoPlayVideos',
    name: 'Auto-play videos',
    category: ['QUEUE MANAGER PLUS', 'Gallery', 'Auto-play videos'],
    tooltip: 'Automatically play videos in the Gallery view.',
    type: 'boolean',
    defaultValue: true,
  },
  {
    id: 'QueueManager.Gallery.HideImagesWhenVideoExists',
    name: 'Hide images when video exists',
    category: ['QUEUE MANAGER PLUS', 'Gallery', 'Hide images when video exists'],
    tooltip: 'If workflow produces both video and images then hide images in the Gallery view.',
    type: 'boolean',
    defaultValue: true,
  },
  {
    id: 'QueueManager.Gallery.ShowVideos',
    name: 'Show videos',
    category: ['QUEUE MANAGER PLUS', 'Gallery', 'Show videos'],
    tooltip: "Show generated videos in the gallery. If you disable both images and videos then Gallery won't show",
    type: 'boolean',
    defaultValue: true,
  },
  {
    id: 'QueueManager.Gallery.ShowImages',
    name: 'Show images',
    category: ['QUEUE MANAGER PLUS', 'Gallery', 'Show images'],
    tooltip: "Show generated videos in the gallery. If you disable both images and videos then Gallery won't show",
    type: 'boolean',
    defaultValue: true,
  },
];
