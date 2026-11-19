#!/usr/bin/env python3
"""Write docs/assets/data/parameters.json (the data of the page "Parameters").

``python scripts/make_parameters_data.py``           rewrite the file
``python scripts/make_parameters_data.py --check``   exit 1 when the file is not up to date

YPhotoSharing has no JSON Schema for its configuration, so the catalogue lives here: every setting that the runtime reads
(with the default it uses when the key is absent), described in English and Italian. ``--check`` also verifies that every
setting listed in ``example/server_config.json`` and ``example/client_config.json`` is in the catalogue, so a new key of the
example cannot go undocumented.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "docs" / "assets" / "data" / "parameters.json"

# (path, kind, default, basic, help_en, help_it[, extra])   kind: bool int float str choice list table kv ranges
SERVER = [
    ("run", "Run and connection", "Esecuzione e connessione", [
        ("server_name", "str", "orchestrator_server", True, "Name of the orchestrator Ray actor; clients find it by this name.", "Nome dell'attore Ray orchestratore; i client lo trovano con questo nome."),
        ("namespace", "str", "yphotosharing", True, "Ray namespace shared by the server and its clients.", "Namespace Ray condiviso dal server e dai suoi client."),
        ("min_to_start", "int", 1, True, "Clients that must be registered before the first round. With several clients the server also waits for all of them at the end of every hour.", "Client che devono essere registrati prima del primo turno. Con più client il server li aspetta tutti anche alla fine di ogni ora.", {"min": 1}),
        ("timeout_seconds", "int", 60, False, "Seconds after which a client that does not answer is considered lost.", "Secondi dopo i quali un client che non risponde è considerato perso.", {"min": 1}),
    ]),
    ("database", "Database", "Database", [
        ("database.type", "choice", "sqlite", False, "Database engine.", "Motore del database.", {"choices": ["sqlite"]}),
        ("database.sqlite.filename", "str", "yphotosharing.db", False, "SQLite file inside the experiment folder.", "File SQLite nella cartella dell'esperimento."),
    ]),
    ("simulation", "Annotations and posting", "Annotazioni e pubblicazione", [
        ("simulation.num_rounds", "int", 48, True, "Hours to simulate (48 = two days, 168 = one week).", "Ore da simulare (48 = due giorni, 168 = una settimana).", {"min": 1}),
        ("simulation.posts_per_round", "int", 5, False, "Reference number of posts per round of the example experiment.", "Numero di riferimento di post per turno dell'esperimento d'esempio.", {"min": 0}),
        ("simulation.enable_sentiment", "bool", False, True, "Store a sentiment score for photos and comments.", "Memorizza un punteggio di sentiment per foto e commenti."),
        ("simulation.enable_emotion_annotation", "bool", True, True, "Store the dominant visual emotion of new photos (photo_emotions).", "Memorizza l'emozione visiva dominante delle nuove foto (photo_emotions)."),
        ("simulation.enable_toxicity", "bool", False, False, "Score captions and comments with the Perspective API (needs perspective_api_key).", "Valuta didascalie e commenti con la Perspective API (serve perspective_api_key)."),
        ("simulation.perspective_api_key", "str", None, False, "Key of the Perspective API; null disables it.", "Chiave della Perspective API; null la disabilita."),
    ]),
    ("logging", "Logs", "Log", [
        ("logging.enable_console_log", "bool", True, False, "Also print the logs on the console.", "Stampa i log anche sulla console."),
        ("logging.enable_server_log", "bool", True, False, "Write <server>_server.log.", "Scrive <server>_server.log."),
        ("logging.enable_actor_log", "bool", True, False, "Write the structured actor log.", "Scrive il log strutturato degli attori."),
        ("logging.enable_request_log", "bool", True, False, "Write the request trace _server.log.", "Scrive la traccia delle richieste _server.log."),
    ]),
    ("human", "Human participants", "Partecipanti umani", [
        ("human.gateway.host", "str", "127.0.0.1", False, "Address where run_gateway.py listens (loopback).", "Indirizzo su cui ascolta run_gateway.py (loopback)."),
        ("human.gateway.port", "int", 0, False, "Port of the gateway; 0 picks a free one and writes it to human_gateway.json.", "Porta del gateway; 0 ne sceglie una libera e la scrive in human_gateway.json.", {"min": 0}),
    ]),
]

CLIENT = [
    ("run", "Run and connection", "Esecuzione e connessione", [
        ("client_id", "str", "client_001", True, "Identifier of this client (distinct for each client of a multi-client run).", "Identificatore di questo client (distinto per ogni client di una run multi-client)."),
        ("server_name", "str", "orchestrator_server", False, "Name of the server actor to connect to.", "Nome dell'attore server a cui connettersi."),
        ("namespace", "str", "yphotosharing", False, "Ray namespace of the server.", "Namespace Ray del server."),
        ("address", "str", "auto", False, "Address of the Ray cluster; auto finds the local one.", "Indirizzo del cluster Ray; auto trova quello locale."),
        ("agents_file", "str", "agents.json", True, "Population file of this client.", "File della popolazione di questo client."),
    ]),
    ("time", "Time and images", "Tempo e immagini", [
        ("simulation.num_rounds", "int", 48, True, "Hours this client plays.", "Ore che questo client gioca.", {"min": 1}),
        ("simulation.start_day", "int", 0, False, "Day on which the clock starts.", "Giorno da cui parte l'orologio.", {"min": 0}),
        ("simulation.num_slots_per_day", "int", 24, False, "Slots (hours) in a day.", "Slot (ore) in un giorno.", {"min": 1}),
        ("simulation.use_local_diffusion", "bool", False, True, "Generate real images locally with Hugging Face diffusers. When on, a post whose image fails is not published.", "Genera immagini reali in locale con Hugging Face diffusers. Se attiva, un post la cui immagine fallisce non è pubblicato."),
        ("simulation.local_diffusion_model", "str", "segmind/tiny-sd", False, "Diffusion model to load.", "Modello di diffusione da caricare."),
    ]),
    ("annotations", "Annotations", "Annotazioni", [
        ("simulation.enable_sentiment", "bool", False, True, "Store sentiment for photos and comments.", "Memorizza il sentiment di foto e commenti."),
        ("simulation.enable_emotion_annotation", "bool", True, True, "Store the visual emotion of new photos.", "Memorizza l'emozione visiva delle nuove foto."),
        ("simulation.enable_toxicity", "bool", False, False, "Toxicity scores from the Perspective API.", "Punteggi di tossicità dalla Perspective API."),
        ("simulation.perspective_api_key", "str", None, False, "Perspective API key.", "Chiave della Perspective API."),
        ("simulation.enable_memory_annotations", "bool", True, True, "Write memory events and load memory context into comments and direct messages.", "Scrive eventi di memoria e carica il contesto di memoria in commenti e messaggi diretti."),
    ]),
    ("topics", "Topics", "Argomenti", [
        ("simulation.discussion_topics", "list", ["general"], True, "Topics that exist in the experiment: agents post about them and build interest profiles on them.", "Argomenti che esistono nell'esperimento: gli agenti vi scrivono e ne costruiscono profili di interesse."),
    ]),
    ("activity", "Who acts and what they do", "Chi agisce e cosa fa", [
        ("simulation.actions_likelihood", "kv", {"post_photo": 0.15, "react": 0.2, "comment": 0.15, "follow": 0.1, "share": 0.05, "report": 0.05, "save": 0.1, "reply_comment": 0.1, "unfollow": 0.05, "send_dm": 0.05, "post_story": 0.05, "watch_story": 0.05}, True, "Weight of each action in the random draw of a session (post_photo, react, comment, follow, share, report, save, reply_comment, unfollow, send_dm, post_story, watch_story). The archetype multiplies some of them.", "Peso di ogni azione nell'estrazione casuale di una sessione (post_photo, react, comment, follow, share, report, save, reply_comment, unfollow, send_dm, post_story, watch_story). L'archetipo ne moltiplica alcuni."),
        ("simulation.activity_profiles", "table", {"high": "0-23", "medium": [8, 9, 12, 13, 18, 19, 20, 21], "low": [19, 20, 21]}, True, "Named profiles: the hours in which an agent with that activity_profile acts (with probability 1).", "Profili con nome: le ore in cui agisce un agente con quell'activity_profile (con probabilità 1)."),
        ("simulation.hourly_activity", "kv", {"0": 0.2, "6": 0.4, "12": 0.9, "18": 1.0, "23": 0.4}, False, "For agents without a profile: probability of acting in each hour (0-23), multiplied by daily_activity_level / 5. The default list peaks in the evening (excerpt shown).", "Per gli agenti senza profilo: probabilità di agire in ogni ora (0-23), moltiplicata per daily_activity_level / 5. L'elenco predefinito ha il picco serale (estratto mostrato)."),
        ("simulation.agent_archetypes", "table", {}, False, "Optional definitions of archetypes; built-in ones are broadcaster, explorer and validator.", "Definizioni facoltative di archetipi; quelli predefiniti sono broadcaster, explorer e validator."),
    ]),
    ("agents", "Follow graph, churn and new users", "Grafo dei follow, abbandono e nuovi utenti", [
        ("simulation.agents.probability_of_secondary_follow", "float", 0.0, True, "After its actions, the probability of following each account the agent interacted with.", "Dopo le sue azioni, la probabilità di seguire ogni account con cui l'agente ha interagito.", {"min": 0, "max": 1}),
        ("simulation.agents.probability_of_follow_back", "float", 0.0, True, "Probability that a public account follows back a new follower.", "Probabilità che un account pubblico ricambi un nuovo follower.", {"min": 0, "max": 1}),
        ("simulation.agents.churn.enabled", "bool", False, True, "End-of-day pass that makes inactive agents leave.", "Passaggio di fine giornata che fa uscire gli agenti inattivi."),
        ("simulation.agents.churn.churn_probability", "float", 0.0, False, "Probability that a sampled candidate leaves.", "Probabilità che un candidato campionato esca.", {"min": 0, "max": 1}),
        ("simulation.agents.churn.inactivity_threshold", "int", 5, False, "Days without activity that make an agent a candidate.", "Giorni senza attività che rendono un agente candidato.", {"min": 1}),
        ("simulation.agents.churn.churn_percentage", "float", 0.0, False, "Share of the candidates that is sampled each day.", "Quota di candidati campionata ogni giorno.", {"min": 0, "max": 1}),
        ("simulation.agents.new_agents.enabled", "bool", False, True, "Add newcomers cloned from existing agents at the end of each day.", "Aggiunge nuovi utenti clonati da agenti esistenti a fine giornata."),
        ("simulation.agents.new_agents.probability_new_agents", "float", 0.0, False, "Chance that each slot spawns a newcomer.", "Probabilità che ogni posto generi un nuovo utente.", {"min": 0, "max": 1}),
        ("simulation.agents.new_agents.percentage_new_agents", "float", 0.0, False, "Share of the active population that gives the number of newcomer slots.", "Quota della popolazione attiva che dà il numero di posti per nuovi utenti.", {"min": 0, "max": 1}),
    ]),
    ("opinion", "Opinion dynamics", "Dinamica delle opinioni", [
        ("simulation.opinion_dynamics.enabled", "bool", False, True, "Update opinions when agents comment or reply.", "Aggiorna le opinioni quando gli agenti commentano o rispondono."),
        ("simulation.opinion_dynamics.model_name", "choice", "bounded_confidence", True, "Opinion model: continuous bounded confidence or Likert evaluation by the language model.", "Modello di opinione: fiducia limitata continua o valutazione Likert del modello linguistico.", {"choices": ["bounded_confidence", "llm_evaluation"]}),
        ("simulation.opinion_dynamics.parameters.epsilon", "float", 0.25, False, "Bounded confidence: largest opinion distance that still attracts.", "Fiducia limitata: massima distanza di opinione che ancora attrae.", {"min": 0, "max": 1}),
        ("simulation.opinion_dynamics.parameters.mu", "float", 0.5, False, "Bounded confidence: fraction of the distance covered at each attraction.", "Fiducia limitata: frazione della distanza coperta a ogni attrazione.", {"min": 0, "max": 1}),
        ("simulation.opinion_dynamics.parameters.theta", "float", 0.0, False, "Bounded confidence: step away from an author beyond epsilon (0 = ignore).", "Fiducia limitata: passo di allontanamento da un autore oltre epsilon (0 = ignora).", {"min": 0, "max": 1}),
        ("simulation.opinion_dynamics.parameters.cold_start", "str", "neutral", False, "What an agent without an opinion does at first contact.", "Cosa fa un agente senza opinione al primo contatto."),
        ("simulation.opinion_dynamics.parameters.evaluation_scope", "str", "interlocutor_only", False, "LLM evaluation: whose messages are considered.", "Valutazione LLM: quali messaggi sono considerati."),
        ("simulation.opinion_dynamics.likert_scale", "list", ["Strongly disagree", "Disagree", "Neutral", "Agree", "Strongly agree"], False, "Ordered classes used by the discrete evaluator.", "Classi ordinate usate dal valutatore discreto."),
        ("simulation.opinion_dynamics.opinion_groups", "ranges", {"Neutral": [0.4, 0.6]}, False, "Label of each class and its score range in [0, 1].", "Etichetta di ogni classe e suo intervallo di punteggio in [0, 1]."),
    ]),
    ("stress", "Stress and reward", "Stress e ricompensa", [
        ("simulation.stress_reward.enabled", "bool", False, True, "Write stress and reward events for the targets of reactions, comments, shares and reports.", "Scrive eventi di stress e ricompensa per i destinatari di reazioni, commenti, condivisioni e segnalazioni."),
        ("simulation.stress_reward.backward_rounds", "int", 24, False, "Rounds replayed to rebuild the current state.", "Turni rigiocati per ricostruire lo stato corrente.", {"min": 1}),
        ("simulation.stress_reward.system.coupling.reward_buffers_stress_alpha", "float", 0.3, False, "A rise of stress is multiplied by 1 − alpha × reward.", "Un aumento di stress è moltiplicato per 1 − alpha × ricompensa.", {"min": 0, "max": 1}),
        ("simulation.stress_reward.system.coupling.stress_reduces_reward_beta", "float", 0.2, False, "A rise of reward is multiplied by 1 − beta × stress.", "Un aumento di ricompensa è moltiplicato per 1 − beta × stress.", {"min": 0, "max": 1}),
        ("simulation.stress_reward.system.churn.enabled", "bool", False, False, "Enable the churn formula of the module.", "Abilita la formula di abbandono del modulo."),
        ("simulation.stress_reward.system.churn.stress_weight", "float", 2.0, False, "Weight of stress in the churn logit.", "Peso dello stress nel logit di abbandono."),
        ("simulation.stress_reward.system.churn.reward_weight", "float", 1.0, False, "Weight of reward in the churn logit.", "Peso della ricompensa nel logit di abbandono."),
        ("simulation.stress_reward.system.churn.bias", "float", -1.8, False, "Bias of the churn logit.", "Bias del logit di abbandono."),
        ("simulation.stress_reward.system.churn.temperature", "float", 0.3, False, "Temperature of the churn sigmoid.", "Temperatura della sigmoide di abbandono.", {"xmin": 0}),
        ("simulation.stress_reward.system.churn.min_probability", "float", 0.0, False, "Floor of the churn probability.", "Soglia minima della probabilità di abbandono.", {"min": 0, "max": 1}),
        ("simulation.stress_reward.system.churn.max_probability", "float", 0.95, False, "Cap of the churn probability.", "Tetto della probabilità di abbandono.", {"min": 0, "max": 1}),
        ("simulation.stress_reward.system.events", "table", {"reaction": {"like": {"stress": -0.005, "reward": 0.03}}}, False, "Deltas of stress and reward per event family and subtype: reaction (like, dislike), comment (positive, neutral, critical, hostile, supportive), share (positive, hostile), report (mass_report). Only the changed ones need to be written.", "Delta di stress e ricompensa per famiglia e sottotipo di evento: reaction (like, dislike), comment (positive, neutral, critical, hostile, supportive), share (positive, hostile), report (mass_report). Basta scrivere quelli cambiati."),
        ("simulation.stress_reward.system.traits", "kv", {"sensitivity": 1.0, "reward_sensitivity": 1.0, "resilience": 1.0, "visibility_need": 1.0}, False, "Default affective traits of an agent.", "Tratti affettivi predefiniti di un agente."),
    ]),
    ("llm", "Language and vision models", "Modelli linguistici e di visione", [
        ("llm.backend", "str", "ollama", True, "Backend of the language model (ollama, vllm or an OpenAI-compatible endpoint).", "Backend del modello linguistico (ollama, vllm o un endpoint compatibile OpenAI)."),
        ("llm.address", "str", "localhost", True, "Host (or full URL) of the model server.", "Host (o URL completo) del server del modello."),
        ("llm.port", "int", 11434, True, "Port of the model server.", "Porta del server del modello.", {"min": 1}),
        ("llm.model", "str", "llama3.2", True, "Model name.", "Nome del modello."),
        ("llm.temperature", "float", 0.7, False, "Sampling temperature.", "Temperatura di campionamento.", {"min": 0}),
        ("llm.use_vllm", "bool", False, False, "Use vLLM for batched local inference.", "Usa vLLM per l'inferenza locale a lotti."),
        ("llm.use_remote_batch", "bool", False, False, "Queue prompts and resolve them in bulk against a remote endpoint.", "Accoda i prompt e li risolve in blocco su un endpoint remoto."),
        ("llm.llm_api_key", "str", None, False, "API key for endpoints that need one (sent as a bearer token).", "Chiave API per gli endpoint che la richiedono (inviata come bearer token)."),
        ("llm.api_format", "choice", "auto", False, "Protocol spoken by the endpoint.", "Protocollo parlato dall'endpoint.", {"choices": ["auto", "openai", "ollama"]}),
        ("llm.max_tokens", "int", None, False, "Cap on generated tokens.", "Tetto ai token generati.", {"min": 1}),
        ("llm.timeout", "int", None, False, "Request timeout in seconds.", "Timeout delle richieste in secondi.", {"min": 1}),
        ("llm_vision.backend", "str", "ollama", False, "Backend of the vision model; omit llm_vision for text-only runs.", "Backend del modello di visione; ometti llm_vision per run solo testo."),
        ("llm_vision.address", "str", "localhost", False, "Host of the vision model server.", "Host del server del modello di visione."),
        ("llm_vision.port", "int", 11434, False, "Port of the vision model server.", "Porta del server del modello di visione.", {"min": 1}),
        ("llm_vision.model", "str", "minicpm-v", False, "Vision model that looks at the generated images.", "Modello di visione che guarda le immagini generate."),
    ]),
    ("logging", "Logs", "Log", [
        ("logging.enable_console_log", "bool", True, False, "Print the logs on the console.", "Stampa i log sulla console."),
        ("logging.enable_execution_log", "bool", True, False, "Write <client>_execution.log.", "Scrive <client>_execution.log."),
        ("logging.enable_actor_log", "bool", True, False, "Write the structured actor log.", "Scrive il log strutturato degli attori."),
        ("logging.enable_action_log", "bool", False, False, "Write a summary line for each action of each agent.", "Scrive una riga di riepilogo per ogni azione di ogni agente."),
        ("logging.enable_prompt_log", "bool", False, False, "Write the prompts sent to the model.", "Scrive i prompt inviati al modello."),
        ("logging.enable_llm_usage_log", "bool", True, False, "Write the model usage accounting.", "Scrive il conteggio dell'uso del modello."),
    ]),
]


def fields(sections):
    out = []
    for sid, en, it, items in sections:
        fs = []
        for item in items:
            path, kind, default, basic, h_en, h_it = item[:6]
            extra = item[6] if len(item) > 6 else {}
            fs.append({"path": path, "kind": kind, "default": default, "min": extra.get("min"), "xmin": extra.get("xmin"), "max": extra.get("max"),
                       "choices": extra.get("choices"), "basic": basic, "label": path, "label_it": path, "help": h_en, "help_it": h_it})
        out.append({"id": sid, "title": en, "title_it": it, "fields": fs})
    return out


def flatten(obj, prefix=""):
    for k, v in obj.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict) and v and not all(isinstance(x, (list, str)) for x in v.values()) and k not in ("actions_likelihood", "hourly_activity", "activity_profiles", "opinion_groups"):
            yield from flatten(v, key + ".")
        else:
            yield key


def catalogue_paths(sections):
    return {i[0] for s in sections for i in s[3]}


#: keys that the example writes at a level the code does not read (the code reads them under ``parameters``): not documented
#: as settings of their own
MISPLACED_IN_EXAMPLE = {"simulation.opinion_dynamics.evaluation_scope"}


def undocumented() -> list:
    missing = []
    for fname, sections in (("server_config.json", SERVER), ("client_config.json", CLIENT)):
        f = ROOT / "example" / fname
        if not f.is_file():
            continue
        known = catalogue_paths(sections)
        for p in flatten(json.loads(f.read_text(encoding="utf-8"))):
            if p not in known and p not in MISPLACED_IN_EXAMPLE and not any(k.startswith(p + ".") for k in known):
                missing.append(f"{fname}: {p}")
    return missing


def build() -> dict:
    return {"server": fields(SERVER), "client": fields(CLIENT)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    text = json.dumps(build(), indent=1, ensure_ascii=False) + "\n"
    missing = undocumented()
    if missing:
        print("not in the catalogue:\n  " + "\n  ".join(missing), file=sys.stderr)
    if args.check:
        return 0 if (OUTPUT.is_file() and OUTPUT.read_text(encoding="utf-8") == text and not missing) else 1
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
