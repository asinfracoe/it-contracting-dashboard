"""
Azure Cosmos DB Client
Manages connections and operations with Cosmos DB
"""

from azure.cosmos import CosmosClient, exceptions, PartitionKey
from azure.cosmos.database import DatabaseProxy
from azure.cosmos.container import ContainerProxy
from typing import Dict, List, Optional, Any
import logging
from datetime import datetime

from config import get_settings
from db.schemas import BOM, ChatSession, Pattern, Template, User, AnalyticsMetric

logger = logging.getLogger(__name__)
settings = get_settings()


class CosmosDBClient:
    """Cosmos DB client wrapper"""
    
    def __init__(self):
        """Initialize Cosmos DB client"""
        self.client: Optional[CosmosClient] = None
        self.database: Optional[DatabaseProxy] = None
        self.containers: Dict[str, ContainerProxy] = {}
        
    def connect(self):
        """Connect to Cosmos DB and auto-provision database + containers."""
        try:
            self.client = CosmosClient(
                settings.cosmos_db_endpoint,
                credential=settings.cosmos_db_key
            )
            # Auto-create database if it doesn't exist
            self.database = self.client.create_database_if_not_exists(
                id=settings.cosmos_db_database
            )
            logger.info(f"Connected to Cosmos DB: {settings.cosmos_db_database}")

            # Auto-create containers then initialise references
            self.create_containers_if_not_exist()
            self._init_containers()

        except Exception as e:
            logger.error(f"Failed to connect to Cosmos DB: {e}")
            raise
    
    def _init_containers(self):
        """Initialize container references"""
        container_names = [
            settings.cosmos_container_sessions,
            settings.cosmos_container_boms,
            settings.cosmos_container_patterns,
            settings.cosmos_container_templates,
            settings.cosmos_container_analytics,
            settings.cosmos_container_users
        ]
        
        for container_name in container_names:
            try:
                self.containers[container_name] = self.database.get_container_client(container_name)
                logger.info(f"Initialized container: {container_name}")
            except exceptions.CosmosResourceNotFoundError:
                logger.warning(f"Container not found: {container_name}")
    
    def create_containers_if_not_exist(self):
        """Create containers if they don't exist"""
        # Sessions container
        try:
            self.database.create_container(
                id=settings.cosmos_container_sessions,
                partition_key=PartitionKey(path="/user_id"),
                default_ttl=86400 * 30  # 30 days TTL
            )
            logger.info(f"Created container: {settings.cosmos_container_sessions}")
        except exceptions.CosmosResourceExistsError:
            pass
        
        # BOMs container
        try:
            self.database.create_container(
                id=settings.cosmos_container_boms,
                partition_key=PartitionKey(path="/project_name")
            )
            logger.info(f"Created container: {settings.cosmos_container_boms}")
        except exceptions.CosmosResourceExistsError:
            pass
        
        # Patterns container
        try:
            self.database.create_container(
                id=settings.cosmos_container_patterns,
                partition_key=PartitionKey(path="/category")
            )
            logger.info(f"Created container: {settings.cosmos_container_patterns}")
        except exceptions.CosmosResourceExistsError:
            pass
        
        # Templates container
        try:
            self.database.create_container(
                id=settings.cosmos_container_templates,
                partition_key=PartitionKey(path="/category")
            )
            logger.info(f"Created container: {settings.cosmos_container_templates}")
        except exceptions.CosmosResourceExistsError:
            pass
        
        # Analytics container
        try:
            self.database.create_container(
                id=settings.cosmos_container_analytics,
                partition_key=PartitionKey(path="/metric_type")
            )
            logger.info(f"Created container: {settings.cosmos_container_analytics}")
        except exceptions.CosmosResourceExistsError:
            pass
        
        # Users container
        try:
            self.database.create_container(
                id=settings.cosmos_container_users,
                partition_key=PartitionKey(path="/user_id")
            )
            logger.info(f"Created container: {settings.cosmos_container_users}")
        except exceptions.CosmosResourceExistsError:
            pass
        
        # Reinitialize container references
        self._init_containers()
    
    # ========================================================================
    # Generic CRUD Operations
    # ========================================================================
    
    def create_item(self, container_name: str, item: Dict[str, Any]) -> Dict[str, Any]:
        """Create an item in a container"""
        try:
            container = self.containers[container_name]
            created_item = container.create_item(body=item)
            logger.info(f"Created item in {container_name}: {item.get('id')}")
            return created_item
        except Exception as e:
            logger.error(f"Error creating item in {container_name}: {e}")
            raise
    
    def read_item(
        self, 
        container_name: str, 
        item_id: str, 
        partition_key: str
    ) -> Optional[Dict[str, Any]]:
        """Read an item from a container"""
        try:
            container = self.containers[container_name]
            item = container.read_item(item=item_id, partition_key=partition_key)
            return item
        except exceptions.CosmosResourceNotFoundError:
            logger.warning(f"Item not found: {item_id} in {container_name}")
            return None
        except Exception as e:
            logger.error(f"Error reading item from {container_name}: {e}")
            raise
    
    def update_item(
        self, 
        container_name: str, 
        item_id: str, 
        item: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update an item in a container"""
        try:
            container = self.containers[container_name]
            item['modified_at'] = datetime.utcnow().isoformat()
            updated_item = container.upsert_item(body=item)
            logger.info(f"Updated item in {container_name}: {item_id}")
            return updated_item
        except Exception as e:
            logger.error(f"Error updating item in {container_name}: {e}")
            raise
    
    def delete_item(
        self, 
        container_name: str, 
        item_id: str, 
        partition_key: str
    ):
        """Delete an item from a container"""
        try:
            container = self.containers[container_name]
            container.delete_item(item=item_id, partition_key=partition_key)
            logger.info(f"Deleted item from {container_name}: {item_id}")
        except Exception as e:
            logger.error(f"Error deleting item from {container_name}: {e}")
            raise
    
    def query_items(
        self, 
        container_name: str, 
        query: str, 
        parameters: Optional[List[Dict[str, Any]]] = None,
        partition_key: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Query items from a container"""
        try:
            container = self.containers[container_name]
            
            if partition_key:
                items = list(container.query_items(
                    query=query,
                    parameters=parameters or [],
                    partition_key=partition_key
                ))
            else:
                items = list(container.query_items(
                    query=query,
                    parameters=parameters or [],
                    enable_cross_partition_query=True
                ))
            
            return items
        except Exception as e:
            logger.error(f"Error querying items from {container_name}: {e}")
            raise
    
    # ========================================================================
    # Specific Operations for BOMs
    # ========================================================================
    
    def create_bom(self, bom: BOM) -> BOM:
        """Create a new BOM"""
        bom_dict = bom.model_dump(by_alias=True, exclude_none=True)
        created = self.create_item(settings.cosmos_container_boms, bom_dict)
        return BOM(**created)
    
    def get_bom(self, bom_id: str, project_name: str) -> Optional[BOM]:
        """Get a BOM by ID"""
        item = self.read_item(settings.cosmos_container_boms, bom_id, project_name)
        return BOM(**item) if item else None
    
    def update_bom(self, bom: BOM) -> BOM:
        """Update a BOM"""
        bom_dict = bom.model_dump(by_alias=True, exclude_none=True)
        updated = self.update_item(settings.cosmos_container_boms, bom.bom_id, bom_dict)
        return BOM(**updated)
    
    def list_boms(
        self, 
        category: Optional[str] = None, 
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[BOM]:
        """List BOMs with optional filters"""
        query = "SELECT * FROM c"
        where_clauses = []
        parameters = []
        
        if category:
            where_clauses.append("c.category = @category")
            parameters.append({"name": "@category", "value": category})
        
        if status:
            where_clauses.append("c.status = @status")
            parameters.append({"name": "@status", "value": status})
        
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        
        query += f" ORDER BY c.created_at DESC OFFSET 0 LIMIT {limit}"
        
        items = self.query_items(settings.cosmos_container_boms, query, parameters)
        return [BOM(**item) for item in items]
    
    # ========================================================================
    # Specific Operations for Chat Sessions
    # ========================================================================
    
    def create_session(self, session: ChatSession) -> ChatSession:
        """Create a new chat session"""
        session_dict = session.model_dump(by_alias=True, exclude_none=True)
        created = self.create_item(settings.cosmos_container_sessions, session_dict)
        return ChatSession(**created)
    
    def get_session(self, session_id: str, user_id: str) -> Optional[ChatSession]:
        """Get a chat session by ID"""
        item = self.read_item(settings.cosmos_container_sessions, session_id, user_id)
        return ChatSession(**item) if item else None
    
    def update_session(self, session: ChatSession) -> ChatSession:
        """Update a chat session"""
        session_dict = session.model_dump(by_alias=True, exclude_none=True)
        updated = self.update_item(settings.cosmos_container_sessions, session.session_id, session_dict)
        return ChatSession(**updated)
    
    # ========================================================================
    # Close connection
    # ========================================================================
    
    def close(self):
        """Close Cosmos DB connection"""
        if self.client:
            # CosmosClient doesn't have explicit close method
            self.client = None
            logger.info("Closed Cosmos DB connection")


# Global Cosmos DB client instance
cosmos_client = CosmosDBClient()


def get_cosmos_client() -> CosmosDBClient:
    """Get Cosmos DB client instance"""
    if not cosmos_client.client:
        cosmos_client.connect()
    return cosmos_client
