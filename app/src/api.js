// Cambiar la URL en .env.production y configurar el gateway una vez recibido el contrato real.
const base=import.meta.env.VITE_API_URL || '/api'
export async function request(path,{method='GET',token,body}={}){
 const response=await fetch(`${base}${path}`,{method,headers:{...(body?{'Content-Type':'application/json'}:{}),...(token?{'Authorization':`Bearer ${token}`}:{})},body:body?JSON.stringify(body):undefined,cache:'no-store'})
 const data=await response.json().catch(()=>({error:'Respuesta no JSON'}))
 if(!response.ok)throw new Error(data.error||`Error HTTP ${response.status}`)
 return data
}
