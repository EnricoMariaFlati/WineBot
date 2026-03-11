import pandas as pd
import re
from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
from rapidfuzz import process

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


class ActionSearchWine(Action):
    def name(self) -> Text:
        return "action_search_wine"

    def _clean_price(self, price_str):
        if not isinstance(price_str, str):
            try:
                return float(price_str)
            except:
                return float('inf')
        # Extract digits and decimal point using regex
        match = re.search(r'\d+(\.\d+)?', price_str)
        if match:
            return float(match.group())
        return float('inf')

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        budget_str = tracker.get_slot("budget")
        grape = tracker.get_slot("grape")
        country = tracker.get_slot("country")

        try:
            df = pd.read_csv("WineDataset.csv")
        except Exception as e:
            return [SlotSet("wine_search_results", "Sorry, I could not read the wine database.")]

        try:
            budget = float(budget_str) if budget_str else float('inf')
        except (ValueError, TypeError):
            budget = float('inf')

        df_filtered = df.copy()
        
        if 'Price' in df_filtered.columns:
            df_filtered['NumericPrice'] = df_filtered['Price'].apply(self._clean_price)
            df_filtered = df_filtered[df_filtered['NumericPrice'] <= budget]

        if grape and 'Grape' in df_filtered.columns:
            str_grape = str(grape).lower()
            df_filtered = df_filtered[df_filtered['Grape'].astype(str).str.lower().str.contains(str_grape, na=False)]

        if country and 'Country' in df_filtered.columns:
            str_country = str(country).lower()
            df_filtered = df_filtered[df_filtered['Country'].astype(str).str.lower().str.contains(str_country, na=False)]

        if df_filtered.empty:
            return [SlotSet("wine_search_results", "I couldn't find any wines matching your criteria.")]

        if len(df_filtered) > 5:
            df_filtered = df_filtered.sort_values(by="NumericPrice", ascending=False).head(5)

        results = []
        for index, row in df_filtered.iterrows():
            title = row.get('Title', 'Unknown Title')
            description = row.get('Description', 'No description available')
            chars = row.get('Characteristics', 'None')
            price = row.get('Price', 'N/A')
            
            wine_info = f"- **{title}**\n  Price: {price}\n  Characteristics: {chars}\n  Description: {description}"
            results.append(wine_info)

        response_text = "\n\n".join(results)
        
        return [SlotSet("wine_search_results", response_text)]
   
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
            "vintage": "The vintage is the year the grapes were harvested. It is crucial because climate variations between years can significantly change the character, quality, and potential of the wine. 📅"        
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

    def run(self, dispatcher, tracker, domain):
        w1 = tracker.get_slot("wine_1")
        w2 = tracker.get_slot("wine_2")
        
        if not w1 or not w2:
            dispatcher.utter_message(text="Please specify the two wines you'd like to compare! 🍷")
            return []

        df = pd.read_csv("WineDataset.csv")
        # logica fuzzy se vuoi precisione!
        wine1_data = df[df['Title'].str.contains(w1, case=False, na=False)]
        wine2_data = df[df['Title'].str.contains(w2, case=False, na=False)]

        if wine1_data.empty or wine2_data.empty:
            dispatcher.utter_message(text="I couldn't find one or both of the wines in the catalog. 🥺")
            return []

        d1 = wine1_data.iloc[0]
        d2 = wine2_data.iloc[0]

        # Creazione della tabella comparativa 
        msg = (f"⚖️ **Comparison: {d1['Title']} vs {d2['Title']}**\n\n"
               f"| Characteristic | {d1['Title']} | {d2['Title']} |\n"
               f"| :--- | :--- | :--- |\n"
               f"| **Price** | {d1.get('Price')} | {d2.get('Price')} |\n"
               f"| **Grape** | {d1.get('Grape')} | {d2.get('Grape')} |\n"
               f"| **Style** | {d1.get('Style')} | {d2.get('Style')} |\n"
               f"| **ABV %** | {d1.get('ABV')} | {d2.get('ABV')} |\n"
               f"| **Origin** | {d1.get('Country')} | {d2.get('Country')} |\n"
               f"| **Region** | {d1.get('Region')} / {d1.get('Appellation')} | {d2.get('Region')} / {d2.get('Appellation')} |\n"
               f"| **Notes** | {d1.get('Characteristics')} | {d2.get('Characteristics')} |\n")
        
        dispatcher.utter_message(text=msg)
        return []