"""
Mock/Dummy Cosmos DB Client
In-memory storage for local development without Azure
"""

from typing import Dict, List, Optional, Any
import logging
from datetime import datetime
import uuid

from db.schemas import BOM, ChatSession, Pattern, Template, User, AnalyticsMetric

logger = logging.getLogger(__name__)


class MockCosmosDBClient:
    """Mock Cosmos DB client using in-memory storage"""
    
    def __init__(self):
        """Initialize mock client with empty collections"""
        self.collections = {
            "sessions": {},
            "boms": {},
            "patterns": {},
            "templates": {},
            "analytics": {},
            "users": {}
        }
        logger.info("Initialized MockCosmosDBClient (in-memory storage)")
        
        # Seed with sample data
        self._seed_sample_data()
    
    def connect(self):
        """Mock connect - always succeeds"""
        logger.info("Mock Cosmos DB connected (no-op)")
    
    def create_containers_if_not_exist(self):
        """Mock container creation - already exists in memory"""
        logger.info("Mock containers created (no-op)")
    
    def _seed_sample_data(self):
        """Seed with sample data for testing"""
        # Sample user
        sample_user = {
            "_id": "user_001",
            "user_id": "user_001",
            "email": "demo@company.com",
            "name": "Demo User",
            "role": "creator",
            "preferences": {},
            "created_at": datetime.utcnow().isoformat()
        }
        self.collections["users"]["user_001"] = sample_user
        
        # Sample template
        sample_template = {
            "_id": "tmpl_datacenter",
            "template_id": "tmpl_datacenter",
            "name": "Data Center / COLO",
            "category": "Data Center",
            "description": "Complete data center infrastructure setup",
            "questions": [
                {
                    "question_id": "q1",
                    "question_text": "How many virtual machines do you need?",
                    "question_type": "number",
                    "help_text": "Typical range: 10-500 VMs"
                },
                {
                    "question_id": "q2",
                    "question_text": "Do you need high availability?",
                    "question_type": "choice",
                    "options": ["Yes - HA pair", "No - Single instance"]
                }
            ],
            "base_items": [],
            "rules": {},
            "example_boms": [],
            "created_by": "system",
            "created_at": datetime.utcnow().isoformat()
        }
        self.collections["templates"]["tmpl_datacenter"] = sample_template
        
        logger.info("Seeded mock database with sample data")
    
    # Generic CRUD Operations
    def create_item(self, container_name: str, item: Dict[str, Any]) -> Dict[str, Any]:
        """Create item in mock storage"""
        item_id = item.get("_id") or item.get("id") or str(uuid.uuid4())
        item["_id"] = item_id
        item["id"] = item_id
        
        self.collections[container_name][item_id] = item
        logger.info(f"Mock created item in {container_name}: {item_id}")
        return item
    
    def read_item(
        self, 
        container_name: str, 
        item_id: str, 
        partition_key: str
    ) -> Optional[Dict[str, Any]]:
        """Read item from mock storage"""
        item = self.collections[container_name].get(item_id)
        if item:
            logger.info(f"Mock read item from {container_name}: {item_id}")
        else:
            logger.warning(f"Mock item not found: {item_id} in {container_name}")
        return item
    
    def update_item(
        self, 
        container_name: str, 
        item_id: str, 
        item: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update item in mock storage"""
        item["modified_at"] = datetime.utcnow().isoformat()
        self.collections[container_name][item_id] = item
        logger.info(f"Mock updated item in {container_name}: {item_id}")
        return item
    
    def delete_item(
        self, 
        container_name: str, 
        item_id: str, 
        partition_key: str
    ):
        """Delete item from mock storage"""
        if item_id in self.collections[container_name]:
            del self.collections[container_name][item_id]
            logger.info(f"Mock deleted item from {container_name}: {item_id}")
    
    def query_items(
        self, 
        container_name: str, 
        query: str, 
        parameters: Optional[List[Dict[str, Any]]] = None,
        partition_key: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Mock query - returns all items in container"""
        # Simplified mock query - just returns all items
        items = list(self.collections[container_name].values())
        logger.info(f"Mock query on {container_name}: returned {len(items)} items")
        return items
    
    # BOM-specific operations
    def create_bom(self, bom: BOM) -> BOM:
        """Create BOM in mock storage"""
        bom_dict = bom.model_dump(by_alias=True, exclude_none=True)
        created = self.create_item("boms", bom_dict)
        return BOM(**created)
    
    def get_bom(self, bom_id: str, project_name: str) -> Optional[BOM]:
        """Get BOM from mock storage"""
        item = self.read_item("boms", bom_id, project_name)
        return BOM(**item) if item else None
    
    def update_bom(self, bom: BOM) -> BOM:
        """Update BOM in mock storage"""
        bom_dict = bom.model_dump(by_alias=True, exclude_none=True)
        updated = self.update_item("boms", bom.bom_id, bom_dict)
        return BOM(**updated)
    
    def list_boms(
        self, 
        category: Optional[str] = None, 
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[BOM]:
        """List BOMs from mock storage"""
        items = self.query_items("boms", "")
        boms = [BOM(**item) for item in items]
        
        # Apply filters
        if category:
            boms = [b for b in boms if b.category == category]
        if status:
            boms = [b for b in boms if b.status == status]
        
        return boms[:limit]
    
    # Session-specific operations
    def create_session(self, session: ChatSession) -> ChatSession:
        """Create session in mock storage"""
        session_dict = session.model_dump(by_alias=True, exclude_none=True)
        created = self.create_item("sessions", session_dict)
        return ChatSession(**created)
    
    def get_session(self, session_id: str, user_id: str) -> Optional[ChatSession]:
        """Get session from mock storage"""
        item = self.read_item("sessions", session_id, user_id)
        return ChatSession(**item) if item else None
    
    def update_session(self, session: ChatSession) -> ChatSession:
        """Update session in mock storage"""
        session_dict = session.model_dump(by_alias=True, exclude_none=True)
        updated = self.update_item("sessions", session.session_id, session_dict)
        return ChatSession(**updated)
    
    def close(self):
        """Mock close - no-op"""
        logger.info("Mock Cosmos DB closed (no-op)")
