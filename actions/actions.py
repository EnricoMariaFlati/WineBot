import pandas as pd
import re
from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.forms import FormValidationAction
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, SessionStarted, ActionExecuted
from rapidfuzz import process, fuzz

class ActionListCharacteristics(Action):
    def name(self) -> Text:
        return "action_list_characteristics"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        try:
            df = pd.read_csv("WineDataset.csv")
        except Exception as e:
            return [SlotSet("characteristics_list", "Sorry, I could not read the wine database.")]

        characteristics_set = set()
        for chars in df['Characteristics'].dropna():
            if isinstance(chars, str):
                for c in chars.split(','):
                    c_clean = c.strip()
                    if c_clean:
                        characteristics_set.add(c_clean)

        unique_chars = sorted(list(characteristics_set))
        if not unique_chars:
            response_text = "No specific characteristics found in the database."
        else:
            response_text = ", ".join(unique_chars)
            
        return [SlotSet("characteristics_list", response_text)]

class ValidateWineSearchForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_wine_search_form"

    async def required_slots(
        self,
        domain_slots: List[Text],
        dispatcher: "CollectingDispatcher",
        tracker: "Tracker",
        domain: "DomainDict",
    ) -> List[Text]:
        return domain_slots.copy()


    def extract_grape(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict
    ) -> Dict[Text, Any]:
        
        text_input = tracker.latest_message.get("text")
        if not text_input:
            return {}
            
        return {"Grape": text_input}


    def extract_characteristics(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict
    ) -> Dict[Text, Any]:
        
        text_input = tracker.latest_message.get("text")
        if not text_input:
            return {}

        import re
        words = re.findall(r'\b\w+\b', text_input.lower())
        
        # Very simple extraction logic based on the text. 
        extracted = []
        for word in words:
            if len(word) > 2 and word not in ["and", "or", "the", "with", "characteristics", "flavors", "tastes"]:
                extracted.append(word.capitalize())
        
        if not extracted:
            return {"Characteristics": text_input} 
            
        # keep max 3
        extracted = extracted[:3]
        return {"Characteristics": ", ".join(extracted)}

    def validate_Price(
        self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> Dict[Text, Any]:
        
        valore_testo = str(slot_value).lower()
        
        # Gestione del caso "non importa"
        if valore_testo in ["any", "dont care", "i don't care", "dont_care"]:
            return {"Price": "any"}
            
        # MAGIA REGEX: Trova tutte le sequenze di numeri nella stringa
        # Se l'utente dice "under 70 dollars", numbers diventerà ['70']
        import re
        numbers = re.findall(r'\d+', valore_testo)
        
        if numbers:
            # Prendiamo il primo numero trovato e lo restituiamo come stringa pulita
            return {"Price": numbers[0]} 
            
        # Se non trova nessun numero (es. l'utente ha scritto "cheap"), resetta lo slot
        return {"Price": None}



class ActionSearchWine(Action):
    def name(self) -> Text:
        return "action_search_wine"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        # 1. CARICAMENTO DEL DATASET
        try:
            # Assicurati che il nome del file CSV sia corretto e si trovi nella root del progetto
            df = pd.read_csv("WineDataset.csv")
        except FileNotFoundError:
            dispatcher.utter_message(text="I'm sorry, I cannot access the wine database right now.")
            return []

        # 2. RECUPERO DEGLI SLOT
        price = tracker.get_slot("Price")
        grape = tracker.get_slot("Grape")
        country = tracker.get_slot("Country")
        characteristics = tracker.get_slot("Characteristics")
        
        # 3. FILTRAGGIO DINAMICO
        filtered_df = df.copy()

        if grape and grape.strip().lower() != "any":
            termine = grape.strip()
            # regex=False previene errori con caratteri speciali
            filtered_df = filtered_df[filtered_df['Grape'].astype(str).str.contains(termine, case=False, regex=False, na=False)]

        if country and country.strip().lower() != "any":
            termine = country.strip()
            filtered_df = filtered_df[filtered_df['Country'].astype(str).str.contains(termine, case=False, regex=False, na=False)]

        if characteristics and characteristics.strip().lower() != "any":
            termine = characteristics.strip()
            filtered_df = filtered_df[filtered_df['Characteristics'].astype(str).str.contains(termine, case=False, regex=False, na=False)]

        if price and str(price).lower() != "any":
            try:
                # 1. Convertiamo il valore dello slot (es. "70") in un numero decimale (float)
                limite_prezzo = float(price)
                
                # 2. Creiamo una colonna temporanea pulita nel dataframe.
                # Questa regex [^\d.] rimuove tutto ciò che NON è un numero o un punto (via i simboli $ o €)
                prezzi_puliti = filtered_df['Price'].astype(str).str.replace(r'[^\d.]', '', regex=True)
                
                # Trasformiamo la colonna pulita in veri numeri (se ci sono errori, mette NaN)
                prezzi_numerici = pd.to_numeric(prezzi_puliti, errors='coerce')
                
                # 3. FILTRO MAGICO: Prendi solo i vini il cui prezzo numerico è <= 70
                filtered_df = filtered_df[prezzi_numerici <= limite_prezzo]
                
            except ValueError:
                # Se qualcosa va storto con la conversione, stampiamo un errore nel terminale (utile per il debug)
                print(f"Errore nella conversione del prezzo: {price}")
        # 4. GESTIONE DEI RISULTATI E OUTPUT
        numero_risultati = len(filtered_df)

        if numero_risultati == 0:
            # SCENARIO A: 0 risultati
            dispatcher.utter_message(
                text="I'm sorry, I couldn't find any wine matching all these specific criteria in my cellar.\nLet's try again! Could you provide different criteria?"
            )

        else:
            # Abbiamo trovato dei risultati! Prepariamo il testo introduttivo e i vini da mostrare
            if 1 <= numero_risultati <= 5:
                # SCENARIO B: Da 1 a 5 risultati (Li mostriamo tutti)
                if numero_risultati == 1:
                    intro = "I found exactly **1 perfect wine** for you:\n\n"
                else:
                    intro = f"Great choices! I found **{numero_risultati} wines** that match your request. Here they are:\n\n"
                vini_da_mostrare = filtered_df

            else:
                # SCENARIO C: Più di 5 risultati (Estraiamo 5 campioni casuali)
                intro = f"We have many wines matching your criteria! I propose 5 of the best ones for you:\n\n"
                vini_da_mostrare = filtered_df.sample(5)

            # --- Ciclo di Formattazione Unico ---
            lista_formattata = intro
            
            for index, vino in vini_da_mostrare.iterrows():
                titolo = vino['Title']
                prezzo = vino['Price']
                paese = vino['Country']
                
                lista_formattata += f"🍷 **{titolo}** | 💰 {prezzo} | 🌍 {paese}\n"
                lista_formattata += "—" * 15 + "\n\n"
            
            # Inviamo il messaggio finale al bot
            dispatcher.utter_message(text=lista_formattata)

        return []


class ActionResetWineSlots(Action):
    def name(self) -> Text:
        return "action_reset_wine_slots"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        # Resettiamo tutti gli slot a None per permettere una nuova ricerca pulita
        return [
            SlotSet("Price", None),
            SlotSet("Grape", None),
            SlotSet("Country", None),
            SlotSet("Characteristics", None)
        ]
   
class ActionWinePairing(Action):
    def name(self) -> Text:
        return "action_wine_pairing"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        # 1. Recuperiamo il cibo dallo slot (es. 'steak', 'chicken', 'cheese')
        food = tracker.get_slot("food")
        
        if not food:
            dispatcher.utter_message(text="Which dish are you planning to eat? 🍽️")
            return []

        try:
            # 2. Carichiamo il dataset DENTRO la funzione
            df = pd.read_csv("WineDataset.csv")
            
            # 3. Cerchiamo il cibo nella colonna 'Description' (o 'Characteristics')
            # Usiamo str.contains per trovare il cibo anche se la descrizione è lunga
            match = df[df['Description'].str.contains(str(food), case=False, na=False) | 
                       df['Characteristics'].str.contains(str(food), case=False, na=False)]
            
            if not match.empty:
                # Prendiamo il nome del primo vino trovato
                wine_title = match.iloc[0]['Title']
                dispatcher.utter_message(text=f"For {food}, I highly recommend: {wine_title}! 🍷✨ Enjoy your meal! 🍽️")
            else:
                dispatcher.utter_message(text=f"I couldn't find a specific pairing for {food} in my collection, but a versatile wine is always a good choice! 🥂")
                
        except Exception as e:
            dispatcher.utter_message(text="Sorry, I had trouble reading the wine database. 🛠️")
            print(f"Errore: {e}")

        return []

class ActionExplainSpecificCharacteristicOfWine(Action):
    def name(self) -> Text:
        return "action_explain_specific_characteristic_of_wine"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        term = tracker.get_slot("term")
        
        # Dizionario delle definizioni
        definitions = {
            "sapid": "A wine is 'sapid' when it has a distinct savory, mineral quality that makes your mouth water. 🌊",
            "tannins": "Tannins are compounds found in grape skins that give wine that drying, 'gripping' sensation. ☕",
            "full-bodied": "A full-bodied wine feels heavy, rich, and 'thick' in your mouth. 🥛",
            "acidity": "Acidity gives wine its freshness and 'zing'. Without it, wine would taste flat. 🍋",
            "savoury": "In our collection, a 'savoury' wine refers to complex, mineral, or earthy notes that evoke a culinary depth. It goes beyond simple fruitiness, offering a structured and layered profile. 🌊",
            "oak-influence": "This refers to the use of oak during maturation. In our collection, it introduces notes of vanilla, cedar, and sweet spices, adding complexity and smoothness to the wine. 🪵",
            "structured": "A 'structured' wine is balanced and complex. Our tasting notes often describe layered bouquets of black fruits and balsamic hints, indicating a wine that is well-built and ready for aging. 🏗️",
            "aromatic": "An 'aromatic' wine has an intense and distinctive olfactory profile. For example, our Viogniers immediately release vibrant notes of apricot, ginger, and cardamom. 🌸",
            "terroir": "Terroir refers to the complete natural environment in which a wine is produced, including factors such as the soil, topography, and climate. It is the 'sense of place' that makes a wine unique to its region. 🌍",
            "finish": "The finish is the lasting impression or aftertaste that remains on your palate after swallowing the wine. A long, pleasant finish is often a sign of high quality and complexity. ⏳",
            "minerality": "Minerality is a sensation in the wine that reminds you of wet stones, flint, or saline notes. It is often found in wines grown in soils with specific geological compositions. 💎",
            "balsamic": "A 'balsamic' note refers to aromas reminiscent of Mediterranean herbs, resin, or sweet, dark woods. It adds a layer of aromatic complexity often found in well-aged, structured reds. 🌿",
            "vintage": "The vintage is the year the grapes were harvested. It is crucial because climate variations between years can significantly change the character, quality, and potential of the wine. 📅",        
            "floral": "A 'floral' wine shows aromas reminiscent of flowers such as rose, jasmine, or orange blossom. It is usually elegant and fragrant. 🌸",
            "citrus": "Citrus notes recall fruits like lemon, lime, or grapefruit. They often signal freshness and lively acidity in the wine. 🍋",
            "stone-fruit": "Stone fruit aromas resemble fruits with a pit, such as peach, apricot, or nectarine. They are common in many aromatic white wines. 🍑",
            "tropical-fruit": "Tropical fruit notes evoke aromas like pineapple, mango, or passion fruit, often found in warm-climate white wines. 🍍",
            "red-fruit": "Red fruit aromas include notes like strawberry, raspberry, and red cherry. They often appear in lighter red wines. 🍓",
            "black-fruit": "Black fruit notes recall blackberry, blackcurrant, and black plum, typical of richer and more powerful red wines. 🍇",
            "cassis": "Cassis refers to the aroma of blackcurrant. It is a classic descriptor often associated with Cabernet Sauvignon wines. 🫐",
            "herbaceous": "An 'herbaceous' wine shows aromas reminiscent of fresh herbs such as basil, mint, or cut grass. 🌿",
            "earthy": "Earthy wines evoke aromas of soil, mushrooms, or forest floor, adding complexity and a natural character. 🌱",
            "forest-floor": "This term refers to aromas reminiscent of damp leaves, mushrooms, and woodland soil, often found in aged red wines. 🍂",
            "spicy": "A spicy wine has aromas reminiscent of spices such as pepper, clove, cinnamon, or nutmeg. 🌶️",
            "peppery": "Peppery wines show notes similar to black or white pepper, commonly found in varieties like Syrah. 🌶️",
            "smoky": "A smoky wine has aromas reminiscent of smoke, toasted wood, or charred elements, often from oak aging or certain terroirs. 🔥",
            "toasty": "Toasty notes recall toasted bread, roasted nuts, or baked pastry, often developed during oak aging or lees aging. 🍞",
            "buttery": "A buttery wine shows creamy aromas reminiscent of butter or cream, often associated with Chardonnay that underwent malolactic fermentation. 🧈",
            "creamy": "A creamy wine has a smooth, rounded mouthfeel and aromas reminiscent of cream, custard, or soft dairy notes. 🥛",
            "cigar-box": "This descriptor refers to aromas of cedar wood and tobacco leaves, often found in aged Cabernet-based wines. 🚬",
            "leathery": "Leathery wines develop aromas reminiscent of leather or saddle, typically appearing as red wines age. 🐎",
            "dried-fruit": "Dried fruit aromas recall raisins, figs, or dried dates, often found in richer or aged wines. 🍇",
            "gooseberry": "Gooseberry is a tart green fruit aroma commonly associated with Sauvignon Blanc wines. 🟢",
            "flinty": "Flinty wines have aromas reminiscent of struck stone or wet flint, often linked to strong minerality. 🪨"
        }

        # Ricerca della definizione
        if term and term.lower() in definitions:
            explanation = definitions[term.lower()]
            dispatcher.utter_message(text=f"Great question! {explanation} 📚🍷")
        else:
            dispatcher.utter_message(text="That's an interesting term! I'm still learning about that, but feel free to ask me about other wine features! 🍇✨")
            
        return []
    
class ActionGetWineDetails(Action):
    def name(self) -> Text:
        return "action_get_wine_details"

    def run(self, dispatcher, tracker, domain):
        wine_name = tracker.get_slot("wine_name")
        
        if not wine_name:
            dispatcher.utter_message(text="Which wine would you like to know about? 🍷")
            return []

        # Carichiamo il CSV
        df = pd.read_csv("WineDataset.csv")
        
        # --- INIZIO MODIFICA FUZZY ---
        # 1. Creiamo una lista di tutti i titoli disponibili nel CSV
        titles = df['Title'].tolist()
        
        # 2. Cerchiamo il titolo più simile a quello inserito dall'utente.
        # score_cutoff=70 significa che la corrispondenza deve essere almeno al 70%
        match = process.extractOne(wine_name, titles, score_cutoff=70)
        
        if match:
            # match[0] è il titolo corretto trovato nel file
            found_title = match[0]
            data = df[df['Title'] == found_title].iloc[0]
            # --- FINE MODIFICA FUZZY ---
            
            # Costruiamo il messaggio con i dettagli del vino
            msg = (f"🔍 **Details for {data['Title']}**:\n\n"
                   f"💰 **Price:** {data.get('Price', 'N/A')}\n"
                   f"🍇 **Grape:** {data.get('Grape', 'N/A')}\n"
                   f"🌍 **Country:** {data.get('Country', 'N/A')}\n"
                   f"📍 **Region/Appellation:** {data.get('Region', 'N/A')} / {data.get('Appellation', 'N/A')}\n"
                   f"📅 **Vintage:** {data.get('Vintage', 'N/A')}\n"
                   f"🍾 **ABV (Alcohol):** {data.get('ABV', 'N/A')}\n"
                   f"✨ **Style:** {data.get('Style', 'N/A')}\n"
                   f"🍷 **Characteristics:** {data.get('Characteristics', 'N/A')}\n\n"
                   f"📝 **Description:** {data.get('Description', 'N/A')}")
            
            dispatcher.utter_message(text=msg)
        else:
            # Se la somiglianza è sotto il 70%, entriamo qui
            dispatcher.utter_message(text=f"Mi dispiace, non ho trovato il vino '{wine_name}' (o qualcosa di simile) nel mio catalogo. 🥺")
            
        return []
    
class ActionCompareWines(Action):
    def name(self) -> Text:
        return "action_compare_wines"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain):
        w1_input = tracker.get_slot("wine_1")
        w2_input = tracker.get_slot("wine_2")
        
        # Load dataset
        df = pd.read_csv("WineDataset.csv")
        titles = df['Title'].tolist()

        # Fuzzy matching logic
        def get_best_match(user_input):
            if not user_input: return None
            match = process.extractOne(user_input, titles, scorer=fuzz.WRatio)
            # Threshold set to 70 for reliability
            return df[df['Title'] == match[0]].iloc[0] if match[1] > 70 else None

        d1 = get_best_match(w1_input)
        d2 = get_best_match(w2_input)

        if d1 is None or d2 is None:
            dispatcher.utter_message(text="I couldn't find one or both of the wines. Please check the spelling and try again! 🍷")
            return []

        # Mobile-friendly comparison layout
        msg = (f"⚖️ *WINE COMPARISON*\n\n"
               f"🍷 *{d1['Title']}*\n"
               f"💰 Price: {d1['Price']}\n"
               f"🍇 Grape: {d1['Grape']}\n"
               f"🌍 Origin: {d1['Country']}\n"
               f"⚡ ABV: {d1['ABV']}\n"
               f"📝 Notes: {str(d1['Characteristics'])[:40]}...\n\n"
               f"--- VS ---\n\n"
               f"🍷 *{d2['Title']}*\n"
               f"💰 Price: {d2['Price']}\n"
               f"🍇 Grape: {d2['Grape']}\n"
               f"🌍 Origin: {d2['Country']}\n"
               f"⚡ ABV: {d2['ABV']}\n"
               f"📝 Notes: {str(d2['Characteristics'])[:40]}...\n\n"
               f"--- ✨ ---\n"
               f"Want to know more? Type: 'Tell me about {d1['Title'][:10]}...' or 'Tell me about {d2['Title'][:10]}...'")
        
        dispatcher.utter_message(text=msg, parse_mode="Markdown")
        return []

class ActionSessionStart(Action):
    def name(self) -> Text:
        return "action_session_start"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        # the session should begin with a `session_started` event
        events = [SessionStarted()]

        # optionally, fetch any slots that we might want to carry over
        for key, value in tracker.slots.items():
            if value is not None:
                events.append(SlotSet(key=key, value=value))

        # trigger the welcome/capabilities message
        dispatcher.utter_message(response="utter_capabilities")

        # an `action_listen` should be added at the end as a user message follows
        events.append(ActionExecuted("action_listen"))

        return events