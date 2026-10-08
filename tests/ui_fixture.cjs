const cp=require('child_process');
const fs=require('fs');
const os=require('os');
const path=require('path');
const net=require('net');

async function server(){
  const folder=fs.mkdtempSync(path.join(os.tmpdir(),'gig-ui-'));
  const socket=net.createServer();
  await new Promise(resolve=>socket.listen(0,'127.0.0.1',resolve));
  const port=socket.address().port;
  await new Promise(resolve=>socket.close(resolve));
  const proc=cp.spawn(path.resolve('.venv/bin/python'),['-m','uvicorn','gig_backend.phone:create_phone_app','--factory','--host','127.0.0.1','--port',String(port),'--no-access-log'],
    {cwd:process.cwd(),env:{...process.env,GIG_DATA_DIR:folder,GIG_MODEL:'',GIG_VISION_MODEL:'',GIG_NVIDIA_API_KEY:'',GIG_OPENCLAW_ENABLE:'0',GIG_OPENCLAW_TOKEN:''},stdio:'ignore'});
  const url=`http://127.0.0.1:${port}`;
  for(let i=0;i<80;i++){
    if(proc.exitCode!==null)break;
    try{if((await fetch(url+'/health')).ok)break;}catch{}
    await new Promise(resolve=>setTimeout(resolve,100));
  }
  if(!fs.existsSync(path.join(folder,'phone-pair-code'))){proc.kill();throw Error('UI fixture failed to start');}
  return {url,code:fs.readFileSync(path.join(folder,'phone-pair-code'),'utf8').trim(),
    cleanup:()=>{proc.kill();fs.rmSync(folder,{recursive:true,force:true});}};
}
module.exports={server};
