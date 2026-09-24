export const API_BASE =
  import.meta.env.VITE_API_BASE_URL ||
  (typeof window !== 'undefined' ? '/api' : 'http://127.0.0.1:9000/api');
export async function api<T=any>(path:string,options:RequestInit={}):Promise<T>{
 const response=await fetch(API_BASE+path,{credentials:'include',...options,
 headers:{...(!options.body || options.body instanceof FormData?{}:{'Content-Type':'application/json'}),...options.headers}});
 const body:any=await response.json().catch(()=>({detail:'The server returned an unreadable response.'}));
 if(!response.ok) throw new Error(typeof body.detail==='string'?body.detail:JSON.stringify(body));
 return body;
}
