/* UI-FOUND-001 — No imports, fetch, XMLHttpRequest, WebSockets,
   storage, analytics, worker calls or live credentials by design.
   Every mutation below changes only in-memory demo state. */
"use strict";

const DEMO = Object.freeze({
  owner: "Pizza Club",
  mode: "LOCAL_DEMO",
  networkEnabled: false
});

const TEAM = {
  aline: { name:"Aline", title:"Chief of Staff", letter:"A", intro:"Entwirf Aufträge für die Unternehmenssteuerung. Eine echte KI-Verbindung besteht nicht." },
  engineering: { name:"Deniz", title:"Engineering", letter:"D", intro:"Hier können Engineering-Aufträge für Reviews, Schnittstellen und Qualitätssicherung formuliert werden." },
  operations: { name:"Samira", title:"Review & Operations", letter:"S", intro:"Dieser Bereich ist ein konzeptioneller Arbeitsraum für die Review-Koordination." },
  sales: { name:"Malik", title:"Sales & Partnerships", letter:"M", intro:"Dieser Bereich zeigt einen möglichen Arbeitsraum für Vertriebsaufträge." },
  people: { name:"Lea", title:"People & AI Workforce", letter:"L", intro:"Dieser Bereich zeigt einen möglichen Arbeitsraum für Mitarbeiter- und Mandatsprüfungen." }
};
const TITLES = {
  ceo:["CEO Cockpit","Unternehmensüberblick mit klar getrennten Demodaten und Entscheidungswegen."],
  aline:["Aline Chat","Dein zentraler Arbeitsraum mit Aline – Aufträge, Entscheidungen und Ergebnisse."],
  tasks:["Aufträge","Auftragsentwürfe und Beispielergebnisse – ohne Verbindung zur Control Plane."],
  approvals:["Freigaben","Simulierte Freigabeabläufe. Es werden keine echten Rechte oder Entscheidungen geändert."],
  costs:["Kosten","Transparente Darstellung von tatsächlicher Demo-Nutzung und unverbindlichen Budgets."],
  engineering:["Engineering","Entwurfsarbeitsraum für Deniz und das Engineering-Team."],
  operations:["Review & Operations","Entwurfsarbeitsraum für Samira."],
  sales:["Sales & Partnerships","Entwurfsarbeitsraum für Malik und Vertrieb."],
  people:["People & AI Workforce","Entwurfsarbeitsraum für Lea und die KI-Belegschaft."]
};

const tasks = [
  {id:"demo-1",title:"Engineering-Statusbericht",description:"Bitte bereite einen Engineering-Statusbericht vor und liste offene CEO-Entscheidungen auf.",owner:"Aline",status:"Entwurf",result:"Kein Ergebnis vorhanden. Ein echter Worker wurde nicht gestartet."},
  {id:"demo-2",title:"API-Schnittstellen prüfen",description:"Konzeptioneller Prüfauftrag für geplante Control-Plane-Endpunkte.",owner:"Deniz",status:"In Prüfung (Demo)",result:"Beispielergebnis, nicht verifiziert: Ein Authentisierungsentscheid und die Implementierung der Fach-API sind noch erforderlich."},
  {id:"demo-3",title:"Beispielbericht erstellen",description:"Demonstration, wie ein fertiggestellter Auftrag dargestellt werden kann.",owner:"Aline",status:"Abgeschlossen (Demo)",result:"Beispielergebnis: Übersicht, Bewertung und Abnahmehinweis erscheinen hier. Es fand keine Ausführung statt."}
];
const approvals = [
  {id:"ap-1",title:"Staging-Änderung vorbereiten",detail:"Freigabemuster für einen künftigen Deployment-Auftrag.",severity:"ÄNDERUNG",status:"Offen"},
  {id:"ap-2",title:"Kostenpflichtigen Worker-Lauf prüfen",detail:"Freigabemuster für einen API-Aufruf mit Budgetgrenze.",severity:"KOSTEN",status:"Offen"}
];

const threads = {
  aline:[
    {role:"assistant",text:"Willkommen im Pizza Club Command Center. Hier kannst du Aufträge formulieren, Ergebnisse ansehen und Freigaben vorbereiten. Dies ist nur ein lokales UI-Demo."},
    {role:"user",text:"Bitte bereite einen Engineering-Statusbericht vor."},
    {role:"assistant",text:"Ein Beispiel-Auftragsentwurf liegt bereit. Für eine echte Ausführung wären Identität, Berechtigungen, Budget und ein genehmigter Ausführungsweg notwendig.",taskId:"demo-1"}
  ],
  engineering:[{role:"assistant",text:"Engineering-Demo: Entwürfe zu Pull Requests, Tests und Architekturfragen sind möglich. Es besteht keine Verbindung zu Deniz oder GitHub."}],
  operations:[{role:"assistant",text:"Review-Demo: Anforderungen, Nachweise und Prüfgates können hier als lokale Entwürfe erfasst werden. Kein Audit wurde durchgeführt."}],
  sales:[{role:"assistant",text:"Sales-Demo: Erstgespräche, Angebote und Partneraufgaben können hier konzeptionell vorbereitet werden. Keine Kundendaten oder Integrationen sind angeschlossen."}],
  people:[{role:"assistant",text:"Workforce-Demo: Mandate, Rollenprofile und Besetzungsanforderungen lassen sich als Entwürfe festhalten. Es erfolgen keine Einstellungen oder Berechtigungsvergaben."}]
};

let currentView="aline";
let nextTask=4;
const byId=id=>document.getElementById(id);
const node=(tag,className,text)=>{
  const element=document.createElement(tag);
  if(className)element.className=className;
  if(text!==undefined)element.textContent=String(text);
  return element;
};
const badge=status=>{
  const b=node("span","state-badge",status);
  if(status==="Offen")b.classList.add("pending");
  if(status==="Genehmigt (Demo)")b.classList.add("approved");
  if(status==="Abgelehnt (Demo)")b.classList.add("rejected");
  return b;
};

function counters(){
  const waiting=approvals.filter(a=>a.status==="Offen").length;
  byId("metricTasks").innerHTML=String(tasks.length).padStart(2,"0")+' <small>Demo</small>';
  byId("metricApprovals").innerHTML=String(waiting).padStart(2,"0")+' <small>Demo</small>';
  byId("taskCount").textContent=tasks.length;
  byId("approvalCount").textContent=waiting;
  byId("railApprovalCount").textContent=waiting;
}

function renderRailApprovals(){
  const root=byId("railApprovals");
  root.replaceChildren();
  const open=approvals.filter(a=>a.status==="Offen");
  if(!open.length){root.append(node("p","no-data","Keine offenen Demo-Freigaben."));return;}
  open.forEach(a=>{
    const card=node("div","rail-approval");
    card.append(node("span","approval-kicker",a.severity+" · DEMO"),node("p","",a.title));
    const button=node("button","","In Demo prüfen");
    button.type="button";
    button.dataset.approval=a.id;
    card.append(button);
    root.append(card);
  });
}

function setActiveView(view){
  if(!TITLES[view])return;
  currentView=view;
  document.querySelectorAll(".nav-item[data-view]").forEach(b=>{
    const active=b.dataset.view===view;
    b.classList.toggle("active",active);
    if(active)b.setAttribute("aria-current","page");
    else b.removeAttribute("aria-current");
  });
  const [title,subtitle]=TITLES[view];
  byId("currentSection").textContent=title;
  byId("pageTitle").replaceChildren(document.createTextNode(view==="ceo"?"Guten Abend, CEO":title+" "),node("span","star","✳"));
  byId("pageSubtitle").textContent=subtitle;
  const conversation=Object.hasOwn(TEAM,view);
  byId("conversationPanel").hidden=!conversation;
  byId("dataPanel").hidden=conversation;
  if(conversation)renderConversation(view);
  else renderDataPanel(view);
  closeSidebar();
}

function renderConversation(view){
  const member=TEAM[view];
  byId("chatTitle").replaceChildren(document.createTextNode(member.name+" "),node("span","secondary-title","/ "+member.title));
  byId("chatAvatar").replaceChildren(document.createTextNode(member.letter),node("span","","✦"));
  byId("chatStatus").textContent="Entwurfsmodus · nicht mit KI verbunden";
  byId("chatInput").placeholder="Schreibe einen lokalen Auftrag an "+member.name+" …";
  renderMessages(view);
}

function renderMessages(view){
  const root=byId("chatMessages");
  root.replaceChildren();
  const day=node("div","day-marker");
  day.append(node("span","","BEISPIELGESPRÄCH · NICHT ECHT"));
  root.append(day);
  (threads[view]||[]).forEach(message=>appendMessage(message,false));
  root.scrollTop=root.scrollHeight;
}

function appendMessage(message,scroll=true){
  const root=byId("chatMessages");
  const isUser=message.role==="user";
  const wrapper=node("div","message-row "+(isUser?"user":"assistant"));
  if(!isUser)wrapper.append(node("div","mini-avatar",TEAM[currentView]?.letter||"A"));
  const content=node("div","message-content");
  const byline=node("div","message-byline");
  byline.append(node("strong","",isUser?"CEO":TEAM[currentView]?.name||"Aline"),node("span","",isUser?"Lokaler Entwurf":"Demoantwort"));
  const bubble=node("div","bubble");
  bubble.append(node("p","",message.text));
  if(message.taskId){
    const task=tasks.find(t=>t.id===message.taskId);
    if(task){
      const proposal=node("div","inline-proposal");
      const desc=node("div");
      desc.append(node("span","inline-proposal-label","ENTWURF · DEMO"),node("strong","",task.title),node("small","","Keine Ausführung · keine API-Kosten"));
      const button=node("button","outline-button","Ansehen →");
      button.type="button";button.dataset.openTask=task.id;
      proposal.append(desc,button);bubble.append(proposal);
    }
  }
  content.append(byline,bubble);wrapper.append(content);root.append(wrapper);
  if(scroll)root.scrollTop=root.scrollHeight;
}

function table(headers){
  const element=node("table","data-table");
  const head=node("thead"),tr=node("tr");
  headers.forEach(h=>tr.append(node("th","",h)));
  head.append(tr);element.append(head,node("tbody"));
  return element;
}
function actionButton(text,handler){
  const b=node("button","table-action",text);
  b.type="button";b.addEventListener("click",handler);return b;
}
function dataHeader(title,description){
  const header=node("div","data-header");
  const copy=node("div");
  copy.append(node("h2","",title),node("p","",description));
  header.append(copy,node("span","data-tag","LOKALES BEISPIEL"));
  return header;
}
function createCard(title,description,meta){
  const c=node("div","simple-card");
  c.append(node("h3","",title),node("p","",description));
  if(meta)c.append(node("small","",meta));
  return c;
}

function renderTasks(panel){
  panel.append(dataHeader("Auftragsübersicht","Der Entwurf ist vom echten WorkItem-Lebenszyklus strikt getrennt."));
  const t=table(["Auftrag","Zuständig (Beispiel)","Status","Ergebnis"]);
  const body=t.querySelector("tbody");
  tasks.forEach(task=>{
    const tr=node("tr");
    tr.append(node("td","",""),node("td","",task.owner),node("td","",""),node("td",""));
    tr.cells[0].append(node("strong","",task.title));
    tr.cells[2].append(badge(task.status));
    tr.cells[3].append(actionButton("Details",()=>showTask(task.id)));
    body.append(tr);
  });
  panel.append(t,createCard("Ergebnisse und Nachweise","Im späteren System: Ergebnis-ID, referenzierter Auftrag, erzeugendes Worker-Subjekt, Zeitpunkt, Artefakte, Prüfer und Abnahmeentscheidung. In der Demo werden ausschließlich erklärende Beispieltexte angezeigt.","Vorgeschlagene Erweiterung · keine API"));
}

function approvalActions(a){
  const actions=node("div","approval-buttons");
  const approve=node("button","","Demo genehmigen");
  const reject=node("button","","Demo ablehnen");
  [approve,reject].forEach(b=>b.type="button");
  approve.addEventListener("click",()=>resolveApproval(a.id,"Genehmigt (Demo)"));
  reject.addEventListener("click",()=>resolveApproval(a.id,"Abgelehnt (Demo)"));
  actions.append(approve,reject);return actions;
}
function renderApprovals(panel){
  panel.append(dataHeader("Entscheidungszentrale","Freigaben verändern nur den lokalen Bildschirmzustand."));
  panel.append(node("p","warning-banner","Keine Genehmigung wird übertragen oder gespeichert. Ein Klick ist niemals eine produktive Autorisierung."));
  approvals.forEach(a=>{
    const c=node("div","simple-card");
    const heading=node("div","data-header");
    heading.style.marginBottom="8px";
    const copy=node("div");copy.append(node("h3","",a.title),node("p","",a.detail));
    heading.append(copy,badge(a.status));c.append(heading);
    c.append(node("small","",a.severity+" · Referenz "+a.id+" · reine Simulation"));
    if(a.status==="Offen")c.append(approvalActions(a));
    panel.append(c);
  });
  panel.append(createCard("Produktives Freigabegate","Erst nach eindeutiger Human-Identität, serverseitiger Berechtigungsprüfung, signierter/gebundener Entscheidung, Budgetprüfung, idempotenter Zustandsänderung und Audit-Trail darf eine echte Aktion ausgelöst werden.","Noch nicht implementiert"));
}
function resolveApproval(id,result){
  const approval=approvals.find(a=>a.id===id);
  if(!approval||approval.status!=="Offen")return;
  if(!window.confirm("Nur Demo: '"+approval.title+"' lokal auf '"+result+"' setzen? Keine echten Änderungen."))return;
  approval.status=result;
  counters();renderRailApprovals();
  if(currentView==="approvals")renderDataPanel("approvals");
}

function renderCosts(panel){
  panel.append(dataHeader("Kosten & Budget","Tatsächliche Demo-Nutzung: keine externen API-Aufrufe."));
  const grid=node("div","cost-grid");
  grid.append(createCard("Verursachte API-Kosten","€ 0,00 – der Prototyp stellt technisch keine Verbindung zu einem Modell oder Backend her.","Nur dieser Prototyp · keine Aussage zu deinem API-Konto"));
  grid.append(createCard("Budgetregel – Entwurf","€ 10,00 als visuelles Beispiel. Es gibt keine persistente Grenze, keine Abrechnung und keine Kostenüberwachung.","NICHT DURCHGESETZT"));
  panel.append(grid);
  const h=node("div","data-header");h.style.marginTop="25px";h.append(node("h2","","Späterer Kostenprozess"));panel.append(h);
  const steps=node("div","flow-steps");
  ["Budget beantragen","Preis schätzen","CEO-Gate","Worker-Ausführung","Usage abgleichen"].forEach((s,i)=>{if(i)steps.append(node("span","flow-arrow","→"));steps.append(node("span","flow-step",s));});
  panel.append(steps,createCard("Keine erfundenen API-Kosten","Ein produktiver Betrag wird erst angezeigt, wenn Provider-Preise, Modellzugriff, gemessener Input/Output-Verbrauch und Kostenaggregationsregeln bekannt sind. Schätzungen und tatsächliche Provider-Abrechnung sind getrennt auszuweisen.","Offener Implementierungs-Gate"));
}

function renderCeo(panel){
  panel.append(dataHeader("Entscheidungen statt Dashboardsilos","Ein Blick über Aufgaben, Ergebnisse, Kosten und die Freigabewarteschlange."));
  panel.append(node("p","warning-banner","Designansicht: keine Echtzeitkennzahlen, keine verbundenen Unternehmensdaten."));
  const grid=node("div","cost-grid");
  const tasksCard=createCard("Auftragsmanagement","Neue Aufträge werden zunächst als lokale Entwürfe erfasst. Später entscheidet die einzelne Assignment Authority über Zuweisungen.","CEO → Aline → Control Plane");
  const approvalsCard=createCard("Freigabekontrolle","Die Demo enthält zwei Beispiel-Freigaben; produktive Entscheidungen sind nicht möglich.","Serverseitige Rechteprüfung erforderlich");
  grid.append(tasksCard,approvalsCard);panel.append(grid);
  panel.append(createCard("Ergebnisse","Abgeschlossene Arbeit soll mit Nachweis, Referenz, Revision, Abnahme und Kosten dargestellt werden. Heute sind nur illustrative Einträge vorhanden.","Kein Worker-Start"));
  panel.append(createCard("Organisationsstruktur","Aline koordiniert die geplanten Abteilungsarbeitsräume. Deniz (Engineering), Samira (Review), Malik (Sales) und Lea (Workforce) dienen als UI-Beispiele. Die endgültigen Rollen und Berechtigungen bleiben separat zu prüfen.","Kein Register oder Mandat geändert"));
}

function renderDataPanel(view){
  const panel=byId("dataPanel");panel.replaceChildren();
  if(view==="tasks")renderTasks(panel);
  else if(view==="approvals")renderApprovals(panel);
  else if(view==="costs")renderCosts(panel);
  else renderCeo(panel);
}
function showTask(id){
  const task=tasks.find(t=>t.id===id);
  if(!task)return;
  byId("dialogTitle").textContent=task.title;
  byId("dialogDescription").textContent=task.description+"\n\n"+task.result;
  byId("dialogStatus").textContent=task.status;
  if(typeof byId("taskDialog").showModal==="function")byId("taskDialog").showModal();
}

function saveLocalDraft(value){
  const text=value.trim();
  if(!text)return;
  const member=TEAM[currentView]||TEAM.aline;
  const task={id:"local-"+nextTask++,title:text.length>65?text.slice(0,62)+"…":text,description:text,owner:member.name,status:"Entwurf",result:"Noch kein Ergebnis. Dieser Auftrag wurde ausschließlich im Arbeitsspeicher des Browsers erstellt."};
  tasks.unshift(task);
  threads[currentView].push({role:"user",text});
  threads[currentView].push({role:"assistant",text:"Dein Auftragsentwurf wurde lokal im Browser angelegt. Für eine tatsächliche Weitergabe wären zunächst die vorgesehenen Sicherheits- und Freigabeschritte nötig.",taskId:task.id});
  appendMessage(threads[currentView][threads[currentView].length-2]);
  appendMessage(threads[currentView][threads[currentView].length-1]);
  counters();
}

function openSidebar(){
  byId("sidebar").classList.add("open");byId("mobileOverlay").hidden=false;
  byId("openSidebar").setAttribute("aria-expanded","true");
}
function closeSidebar(){
  byId("sidebar").classList.remove("open");byId("mobileOverlay").hidden=true;
  byId("openSidebar").setAttribute("aria-expanded","false");
}

document.addEventListener("click",event=>{
  const v=event.target.closest("[data-view]");
  if(v){setActiveView(v.dataset.view);return;}
  const p=event.target.closest("[data-prompt]");
  if(p){
    setActiveView(currentView in TEAM?currentView:"aline");
    const input=byId("chatInput");input.value=p.dataset.prompt;input.focus();return;
  }
  const t=event.target.closest("[data-open-task]");
  if(t){showTask(t.dataset.openTask);return;}
  const a=event.target.closest("[data-approval]");
  if(a){setActiveView("approvals");return;}
});
byId("chatForm").addEventListener("submit",event=>{
  event.preventDefault();
  const input=byId("chatInput");
  saveLocalDraft(input.value);
  input.value="";input.focus();
});
byId("newTaskButton").addEventListener("click",()=>{
  setActiveView("aline");
  byId("chatInput").focus();
});
byId("openSidebar").addEventListener("click",openSidebar);
byId("closeSidebar").addEventListener("click",closeSidebar);
byId("mobileOverlay").addEventListener("click",closeSidebar);
document.addEventListener("keydown",event=>{if(event.key==="Escape")closeSidebar();});
counters();
renderRailApprovals();
