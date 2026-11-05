import {defineConfig} from '@playwright/test'
export default defineConfig({
  testDir:'./tests/e2e', workers:1, timeout:30000,
  use:{baseURL:'http://127.0.0.1:1421',viewport:{width:1366,height:900},
    launchOptions:process.env.TEST_BROWSER_PATH?{executablePath:process.env.TEST_BROWSER_PATH}:{},
  },
  webServer:[
    {command:`${process.platform==='win32'?'python':'python3'} ../tests/e2e_server.py`,url:'http://127.0.0.1:8878/api/health',reuseExistingServer:false},
    {command:'npm run dev -- --port 1421',url:'http://127.0.0.1:1421',env:{VITE_API_URL:'http://127.0.0.1:8878/api'},reuseExistingServer:false},
  ],
})
