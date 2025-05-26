import mesop as me
from dataclasses import dataclass
from dataclasses import field
import google.auth
from google.auth.transport.requests import Request
import requests

@dataclass
class AppConfig:
      vertexai_project_id = "genai-app-builder"
      app_engine = "genai-retail_1697838978813"


## this class represents single result set item - modify it if your results set includes different fields
@dataclass
class SearchResult:
    id: str = "" # Unique product ID
    title: str = ""
    description: str = ""
    price: float = 0.0
    currency: str = ""
    image_url: str = ""
    relevance_score: float = 0.0
    index: int = -1 # For display order

## this class represents view state 
@me.stateclass
class SearchState:
  search_query: str
  search_chunks: list[SearchResult] = field(default_factory=lambda: [])
  search_summary: str


## this class abstracts communication with Veretx AI Search using REST API
class DatastoreService:
    def __init__(self, vertexai_project_id, app_engine):
        ## Here we assume the code will be executed from GCP compute represented by service account with proper role to call Veretx AI Search apps
        creds, project_id = google.auth.default()
        auth_req = Request()  # Use google.auth here
        creds.refresh(auth_req)
        access_token = creds.token
        self.access_token = access_token
        self.vertexai_project_id=vertexai_project_id
        self.app_engine=app_engine

    def search(self, query):
        # Define API endpoint and headers
        url = f"https://discoveryengine.googleapis.com/v1alpha/projects/{self.vertexai_project_id}/locations/global/collections/default_collection/engines/{self.app_engine}/servingConfigs/default_search:search"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

        data = {
            "query": f"{query}",
            "pageSize": 20, ## how many results showuld be deisplayed under summary---
            "queryExpansionSpec": {"condition": "AUTO"},
            "spellCorrectionSpec": {"mode": "AUTO"},
            "contentSearchSpec": {
                "summarySpec": {
                    "ignoreAdversarialQuery": True,
                    "includeCitations": False,
                    "summaryResultCount": 10,   ## how many results should be taken into account when generating summarization
                    "languageCode": "pl"
                }
            }
        }

        # Make POST request
        response = requests.post(url, headers=headers, json=data)
        return response.json()


_datastore_service = DatastoreService(AppConfig.vertexai_project_id, AppConfig.app_engine)

## handlers
def on_search_input_change(e: me.InputEvent):
    """
    Handles changes in the search input field.
    Updates the search_query in the Mesop state.
    """
    state = me.state(SearchState)
    state.search_query = e.value
    # You might want to clear search_chunks and summary here if you want
    # results to disappear as the user types a new query.
    state.search_chunks = []
    state.search_summary = ""

def on_search_button_click(e: me.ClickEvent):
    """
    Handles the search button click event.
    Performs the Vertex AI search and updates the state with results.
    """
    state = me.state(SearchState)
    query = state.search_query

    try:
        results_json = _datastore_service.search(query=query)
        ##print("Search API Response:", results_json) # Keep this for debugging

        summary_text = ""
        if 'summary' in results_json and 'summaryText' in results_json['summary']:
            summary_text = results_json['summary']['summaryText']

        search_results_processed = []
        if 'results' in results_json:
            for i, result in enumerate(results_json['results']):
                doc_id = result.get('id', '')
                document_data = result.get('document', {}).get('structData', {})
                relevance_score = result.get('modelScores', {}).get('relevance_score', {}).get('values', [0.0])[0]

                # Extract product specific data from structData
                title = document_data.get('title', 'N/A').replace('**', '') # Remove markdown bold
                description = document_data.get('description', 'Brak opisu.').replace('**', '') # Remove markdown bold
                price = document_data.get('price', 0.0)
                currency = document_data.get('currency', 'PLN')
                image_url = document_data.get('image', '')

                search_results_processed.append(
                    SearchResult(
                        id=doc_id,
                        title=title.strip(),
                        description=description.strip(),
                        price=float(price),
                        currency=currency,
                        image_url=image_url,
                        relevance_score=float(relevance_score),
                        index=i + 1
                    )
                )

        state.search_chunks = search_results_processed
        state.search_summary = summary_text.strip()
    except Exception as e:
        print(f"Unexpected error: {e}")


### this is where we code UI elements
@me.page(path="/")
def app():
  searchState = me.state(SearchState)

  ## main dev box
  with me.box(style=me.Style(padding=me.Padding(top=20), display="flex", flex_direction="row", gap=100)):
                with me.box(style=me.Style(padding=me.Padding(left=20))):
                    ##search bar
                    with me.box(style=me.Style(display="flex", flex_direction="row", gap=12)):
                        ## search bar
                        me.input(style=me.Style(background="white", width=700),
                                 on_input=on_search_input_change,
                                 )
                        ##search button
                        me.button("Search", type="flat",
                                  on_click=on_search_button_click,
                                  disabled=len(searchState.search_query) == 0
                                  )
                    ##summary
                    me.box(style=me.Style(padding=me.Padding(top=20)))
                    with me.box(style=me.Style(padding=me.Padding(top=20), 
                              background="#F6FCC5", 
                              width=700, 
                              display=("none" if len(searchState.search_summary) == 0 else "flex")
                          )):  ## summary
                          me.markdown(text=searchState.search_summary)
                    ## Search Results Section
                    with me.box(style=me.Style(padding=me.Padding(top=20))):
                        if not searchState.search_chunks and searchState.search_query.strip():
                            # Show a message if no results found for a non-empty query
                            me.text("No results found for your search.", style=me.Style(width=700))
                        elif searchState.search_chunks:
                            for res in searchState.search_chunks:
                                with me.box(style=me.Style(padding=me.Padding(top=15,bottom=15,left=15,right=15),
                                                            margin=me.Margin(bottom=15),
                                                            ##border=me.Border(color="#e0e0e0", width=1),
                                                            border_radius=8,
                                                            background="white",
                                                            width=700,
                                                            display="flex",
                                                            flex_direction="row",
                                                            gap=20,
                                                            align_items="center" # Align items vertically in center
                                                          )):
                                    # Product Image
                                    if res.image_url:
                                        me.image(src=res.image_url,
                                                 alt=res.title,
                                                 style=me.Style(width=100, height=100, object_fit="contain", border_radius=4))

                                    with me.box(style=me.Style(flex_grow=1, display="flex", flex_direction="column", gap=5)):
                                        # Title and Rank Score
                                        with me.box(style=me.Style(display="flex", justify_content="space_between", align_items="baseline")):
                                            me.text(text=res.title, type="headline-6", style=me.Style(font_weight="bold"))

                                        # Price
                                        me.text(text=f"Price: {res.price:.2f} {res.currency}", type="subtitle-1", style=me.Style(font_weight="bold", color="#28a745"))

                                        # Description
                                        me.text(text=res.description, type="body-2", style=me.Style(color="#555"))

