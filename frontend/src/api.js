// Centralized API client: the UI talks to the existing FastAPI backend through these functions.
const API_BASE=import.meta.env.VITE_API_BASE_URL||""; // Empty means same origin when FastAPI serves the built frontend.
async function request(path,options={}){
  const r=await fetch(`${API_BASE}${path}`,{headers:{"Content-Type":"application/json",...(options.headers||{})},...options});
  const text=await r.text(); let data=null; try{data=text?JSON.parse(text):null}catch{data=text}
  if(!r.ok) throw new Error(data?.detail||`Request failed: ${r.status}`); return data;
}
export const api={
 health:()=>request("/health"),
 createUser:b=>request("/users",{method:"POST",body:JSON.stringify(b)}),
 startKyc:id=>request(`/kyc/start/${id}`,{method:"POST"}),
 advanceKyc:id=>request(`/kyc/${id}/advance`,{method:"POST"}),
 getKyc:id=>request(`/kyc/${id}`),
 createAccount:b=>request("/accounts",{method:"POST",body:JSON.stringify(b)}),
 getAccounts:id=>request(`/accounts/${id}`),
 deposit:(id,b)=>request(`/accounts/${id}/deposit`,{method:"POST",body:JSON.stringify(b)}),
 freezeCard:id=>request(`/cards/${id}/freeze`,{method:"POST"}),
 unfreezeCard:id=>request(`/cards/${id}/unfreeze`,{method:"POST"}),
 fxQuote:b=>request("/fx/quote",{method:"POST",body:JSON.stringify(b)}),
 transfer:(b,key)=>request("/transfers",{method:"POST",headers:{"Idempotency-Key":key},body:JSON.stringify(b)}),
 createOrder:b=>request("/trading/orders",{method:"POST",body:JSON.stringify(b)}),
 listAgents:()=>request("/agents")
};
export async function bootstrapDemo(){
  const saved=localStorage.getItem("fintech_demo_user_id");
  if(saved) return Number(saved);

  const email="demo@fintech.local";
  let user;
  try{
    user=await request("/users",{method:"POST",body:JSON.stringify({email,jurisdiction:"PK"})});
  }catch(err){
    // If the demo user already exists, find its ID through the local bootstrap endpoint.
    user=await request(`/demo/bootstrap?email=${encodeURIComponent(email)}`);
  }
  localStorage.setItem("fintech_demo_user_id",String(user.id));
  return user.id;
}
