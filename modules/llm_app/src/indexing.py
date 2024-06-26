# Configure AI Search
from azure.identity import ManagedIdentityCredential
from azure.core.credentials import AzureKeyCredential
import os

from azure.search.documents.indexes import SearchIndexerClient, SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndexerDataContainer, 
    SearchIndexerDataSourceConnection,
    SearchField,
    SearchFieldDataType,
    VectorSearch,
    HnswAlgorithmConfiguration,
    HnswParameters,
    VectorSearchAlgorithmMetric,
    ExhaustiveKnnAlgorithmConfiguration,
    ExhaustiveKnnParameters,
    VectorSearchProfile,
    AzureOpenAIVectorizer,
    AzureOpenAIParameters,
    SemanticConfiguration,
    SemanticSearch,
    SemanticPrioritizedFields,
    SemanticField,
    SearchIndex,
    SplitSkill,
    InputFieldMappingEntry,
    OutputFieldMappingEntry,
    AzureOpenAIEmbeddingSkill,
    SearchIndexerIndexProjections,
    SearchIndexerIndexProjectionSelector,
    SearchIndexerIndexProjectionsParameters,
    IndexProjectionMode,
    SearchIndexerSkillset,
    SearchIndexer,
    FieldMapping,
)
from azure.search.documents.indexes._generated.models import NativeBlobSoftDeleteDeletionDetectionPolicy

# Load environment variables
endpoint = os.environ["AZURE_SEARCH_SERVICE_ENDPOINT"]
credential = ManagedIdentityCredential()
blob_container_name = "rag"
blob_connection_string = f"ResourceId={os.environ["BLOB_RESOURCE_ID"]};" 
azure_openai_endpoint = os.environ["AZURE_OPENAI_ENDPOINT"]
azure_openai_embedding_deployment = "text-embedding-ada-002"
azure_openai_embedding_model_name = "text-embedding-ada-002"
index_name = "vegetables"
resource_group = os.environ["AZURE_RESOURCE_GROUP"]
storage_account_name = os.environ["AZURE_STORAGE_ACCOUNT_NAME"]
subscription_id = os.environ["AZURE_SUBSCRIPTION_ID"]

# Approve private link connections
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.storage import StorageManagementClient

print("------------- Approve private link connections ------------------")
# network_client = NetworkManagementClient(credential, subscription_id)
storage_client = StorageManagementClient(credential, subscription_id)
private_endpoint_connections = storage_client.private_endpoint_connections.list(resource_group, storage_account_name)
for connection in private_endpoint_connections:
    print(f"connection: {connection}")
    if connection.private_link_service_connection_state.status != "Approved":
        response = storage_client.private_endpoint_connections.put(
            resource_group_name=resource_group,
            account_name=storage_account_name,
            private_endpoint_connection_name=connection.name,
            properties={
                "properties": {"privateLinkServiceConnectionState": {"description": "Approved during deployment", "status": "Approved"}}
            },
        )
        print(f"Approved connection: {connection.name}")

# Create a data source 
print("------------- Creating data source ------------------")
indexer_client = SearchIndexerClient(endpoint, credential)
container = SearchIndexerDataContainer(name=blob_container_name)
data_source_connection = SearchIndexerDataSourceConnection(
    name="vegetables",
    type="azureblob",
    container=container,
    connection_string=blob_connection_string,
    data_deletion_detection_policy=NativeBlobSoftDeleteDeletionDetectionPolicy(),
    data_to_extract="storageMetadata"
)
data_source = indexer_client.create_or_update_data_source_connection(data_source_connection)

# Create a search index  
print("------------- Creating search index ------------------")
index_client = SearchIndexClient(endpoint=endpoint, credential=credential)  
fields = [  
    SearchField(name="parent_id", type=SearchFieldDataType.String, sortable=True, filterable=True, facetable=True),  
    SearchField(name="title", type=SearchFieldDataType.String),  
    SearchField(name="chunk_id", type=SearchFieldDataType.String, key=True, sortable=True, filterable=True, facetable=True, analyzer_name="keyword"),  
    SearchField(name="chunk", type=SearchFieldDataType.String, sortable=False, filterable=False, facetable=False),  
    SearchField(name="vector", type=SearchFieldDataType.Collection(SearchFieldDataType.Single), vector_search_dimensions=1536, vector_search_profile_name="myHnswProfile"),  
]  
  
# Configure the vector search configuration  
vector_search = VectorSearch(  
    algorithms=[  
        HnswAlgorithmConfiguration(  
            name="myHnsw",  
            parameters=HnswParameters(  
                m=4,  
                ef_construction=400,  
                ef_search=500,  
                metric=VectorSearchAlgorithmMetric.COSINE,  
            ),  
        ),  
        ExhaustiveKnnAlgorithmConfiguration(  
            name="myExhaustiveKnn",  
            parameters=ExhaustiveKnnParameters(  
                metric=VectorSearchAlgorithmMetric.COSINE,  
            ),  
        ),  
    ],  
    profiles=[  
        VectorSearchProfile(  
            name="myHnswProfile",  
            algorithm_configuration_name="myHnsw",  
            vectorizer="myOpenAI",  
        ),  
        VectorSearchProfile(  
            name="myExhaustiveKnnProfile",  
            algorithm_configuration_name="myExhaustiveKnn",  
            vectorizer="myOpenAI",  
        ),  
    ],  
    vectorizers=[  
        AzureOpenAIVectorizer(  
            name="myOpenAI",  
            kind="azureOpenAI",  
            azure_open_ai_parameters=AzureOpenAIParameters(  
                resource_uri=azure_openai_endpoint,  
                deployment_id=azure_openai_embedding_deployment,  
                model_name=azure_openai_embedding_model_name,
            ),  
        ),  
    ],  
)  
  
semantic_config = SemanticConfiguration(  
    name="my-semantic-config",  
    prioritized_fields=SemanticPrioritizedFields(  
        content_fields=[SemanticField(field_name="chunk")]  
    ),  
)  
  
# Create the semantic search with the configuration  
semantic_search = SemanticSearch(configurations=[semantic_config])  
  
# Create the search index
index = SearchIndex(name=index_name, fields=fields, vector_search=vector_search, semantic_search=semantic_search)  
result = index_client.create_or_update_index(index)  

# Create a skillset  
print("------------- Creating skillsets ------------------")
skillset_name = f"{index_name}-skillset"  
  
split_skill = SplitSkill(  
    description="Split skill to chunk documents",  
    text_split_mode="pages",  
    context="/document",  
    maximum_page_length=2000,  
    page_overlap_length=500,  
    inputs=[  
        InputFieldMappingEntry(name="text", source="/document/content"),  
    ],  
    outputs=[  
        OutputFieldMappingEntry(name="textItems", target_name="pages")  
    ],  
)  
  
embedding_skill = AzureOpenAIEmbeddingSkill(  
    description="Skill to generate embeddings via Azure OpenAI",  
    context="/document/pages/*",  
    resource_uri=azure_openai_endpoint,  
    deployment_id=azure_openai_embedding_deployment, 
    model_name=azure_openai_embedding_model_name, 
    inputs=[  
        InputFieldMappingEntry(name="text", source="/document/pages/*"),  
    ],  
    outputs=[  
        OutputFieldMappingEntry(name="embedding", target_name="vector")  
    ],  
)  
  
index_projections = SearchIndexerIndexProjections(  
    selectors=[  
        SearchIndexerIndexProjectionSelector(  
            target_index_name=index_name,  
            parent_key_field_name="parent_id",  
            source_context="/document/pages/*",  
            mappings=[  
                InputFieldMappingEntry(name="chunk", source="/document/pages/*"),  
                InputFieldMappingEntry(name="vector", source="/document/pages/*/vector"),  
                InputFieldMappingEntry(name="title", source="/document/metadata_storage_name"),  
            ],  
        ),  
    ],  
    parameters=SearchIndexerIndexProjectionsParameters(  
        projection_mode=IndexProjectionMode.SKIP_INDEXING_PARENT_DOCUMENTS  
    ),  
)  
  
skillset = SearchIndexerSkillset(  
    name=skillset_name,  
    description="Skillset to chunk documents and generating embeddings",  
    skills=[split_skill, embedding_skill],  
    index_projections=index_projections,  
)  
  
client = SearchIndexerClient(endpoint, credential)  
client.create_or_update_skillset(skillset)  

# Create an indexer  
print("------------- Creating indexer ------------------")
indexer_name = f"{index_name}-indexer"  
  
indexer = SearchIndexer(  
    name=indexer_name,  
    description="Indexer to index documents and generate embeddings",  
    # skillset_name=skillset_name,  
    target_index_name=index_name,  
    data_source_name="vegetables",  
    # Map the metadata_storage_name field to the title field in the index to display the PDF title in the search results  
    field_mappings=[FieldMapping(source_field_name="metadata_storage_name", target_field_name="title")]  
)  
  
indexer_client = SearchIndexerClient(endpoint, credential)  
indexer_result = indexer_client.create_or_update_indexer(indexer)  
  
# Run the indexer  
indexer_client.run_indexer(indexer_name)  

# Fix Web App startup configuration
print("------------- Fixing WebApp startup configuration ------------------")
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.web import WebSiteManagementClient

subscription_id = os.environ["AZURE_SUBSCRIPTION_ID"]
resource_group_name = os.environ["AZURE_RESOURCE_GROUP"]
app_name = os.environ["AZURE_APP_NAME"]
startup_file = "python3 -m gunicorn app:app"

# Create clients
resource_client = ResourceManagementClient(credential, subscription_id)
web_client = WebSiteManagementClient(credential, subscription_id)

# Get the web app
web_app = web_client.web_apps.get(resource_group_name, app_name)

# Update the startup file
web_app.site_config.app_command_line = startup_file
web_client.web_apps.create_or_update(resource_group_name, app_name, web_app)