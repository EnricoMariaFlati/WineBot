from typing import Any, Text, Dict, List
import pandas as pd
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher

class ActionSearchWine(Action):
    def name(self) -> Text:
        return "action_search_wine"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        # Legge il file wine.csv dalla root del progetto
        try:
            df = pd.read_csv("WineDataset.csv")
        except FileNotFoundError:
            dispatcher.utter_message(text="Error: The wine database (WineDataset.csv) was not found.")
            return []
        
        # Estrae gli slot riempiti dall'utente
        grape = tracker.get_slot("grape")
        wine_type = tracker.get_slot("wine_type")
        country = tracker.get_slot("country")
        
        # Filtra il dataframe
        results = df
        if grape:
            results = results[results['Grape'].str.contains(grape, case=False, na=False)]
        if wine_type:
            results = results[results['Type'].str.contains(wine_type, case=False, na=False)]
        if country:
            results = results[results['Country'].str.contains(country, case=False, na=False)]
        
        # Risponde all'utente
        if not results.empty:
            wine_name = results.iloc[0]['Title']
            dispatcher.utter_message(text=f"I found this wine for you: {wine_name}")
        else:
            dispatcher.utter_message(text="Sorry, I couldn't find a wine with those characteristics.")
            
        return []