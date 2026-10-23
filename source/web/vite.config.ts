import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig(({mode})=>{
 const env=loadEnv(mode,'..','');
 return {envDir:'..',plugins:[react()],server:{proxy:env.VITE_API_BASE_URL?undefined:{
  '/api/auth':{target:'http://localhost:8001',changeOrigin:true,rewrite:p=>p.replace(/^\/api\/auth/,'')},
  '/api/content':{target:'http://localhost:8002',changeOrigin:true,rewrite:p=>p.replace(/^\/api\/content/,'')},
  '/api/audio':{target:'http://localhost:8003',changeOrigin:true,rewrite:p=>p.replace(/^\/api\/audio/,'')}
 }}};
});