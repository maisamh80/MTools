export class Client {
  async call(method, params = {}) {
    if (!this.nonce) {
      const session = await fetch('/mtools/v1/session', {headers: {'X-MTools-Client': '1'}});
      if (!session.ok) throw new Error('M Tools local bridge is unavailable');
      this.nonce = (await session.json()).nonce;
    }
    const response = await fetch('/mtools/v1/rpc', {
      method: 'POST', headers: {'Content-Type': 'application/json', 'X-MTools-Nonce': this.nonce},
      body: JSON.stringify({method, params})
    });
    const data = await response.json();
    if (!response.ok || data.error) throw new Error(data.error || `Request failed (${response.status})`);
    return data.result;
  }
  async upload(file) {
    if(!this.nonce)await this.call('status');
    const response=await fetch('/mtools/v1/project-upload',{method:'POST',headers:{'X-MTools-Nonce':this.nonce,'Content-Type':'application/octet-stream'},body:file});
    if(!response.ok)throw new Error('File upload failed: '+response.status);
    return (await response.json()).token;
  }
  projectMedia(id,path,download=false){return `/mtools/v1/project-media/${encodeURIComponent(id)}?path=${encodeURIComponent(path)}${download?'&download=1':''}`;}
  media(id) { return `/mtools/v1/media/${encodeURIComponent(id)}`; }
  clearSession() { return this.call('session.clear'); }
}
