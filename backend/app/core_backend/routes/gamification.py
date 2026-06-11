from fastapi import APIRouter
from app.core_backend.models.schema import GamificationXP
from app.core_backend.database.supabase_db import DatabaseManager

router = APIRouter()
db = DatabaseManager()

@router.post("/add-xp")
def add_xp(data: GamificationXP):
    db.add_xp(data.user_id, data.amount)
    return {"status": "success", "total_xp": 2450 + data.amount}

@router.get("/leaderboard")
def get_leaderboard():
    real_scores = db.get_leaderboard(limit=10)
    
    # Mock data to fill the leaderboard for testing/demo purposes
    mock_users = [
        {"id": "mock_1", "user_id": "mock_1", "name": "Sarah Chen", "xp": 14500, "badges": 42},
        {"id": "mock_2", "user_id": "mock_2", "name": "David Park", "xp": 13200, "badges": 38},
        {"id": "mock_3", "user_id": "mock_3", "name": "Elena Rodriguez", "xp": 12850, "badges": 35},
        {"id": "mock_4", "user_id": "mock_4", "name": "James Wilson", "xp": 11400, "badges": 31},
        {"id": "mock_5", "user_id": "mock_5", "name": "Aisha Patel", "xp": 10900, "badges": 29},
        {"id": "mock_6", "user_id": "mock_6", "name": "Marcus Johnson", "xp": 9800, "badges": 26},
        {"id": "mock_7", "user_id": "mock_7", "name": "Yuki Tanaka", "xp": 9200, "badges": 24},
        {"id": "mock_9", "user_id": "mock_9", "name": "Liam Smith", "xp": 8100, "badges": 19},
        {"id": "mock_10", "user_id": "mock_10", "name": "Emma Davis", "xp": 7600, "badges": 15},
    ]
    
    # Merge real scores with mock scores
    combined = []
    
    # Format real scores (using user_id suffix as name if name unknown)
    for score in real_scores:
        combined.append({
            "id": score["id"],
            "user_id": score["user_id"],
            "name": f"Scientist {str(score['user_id'])[:4].upper()}", 
            "xp": score["xp"],
            "badges": int(score["xp"] / 500) # Give them roughly 1 badge per 500 xp
        })
        
    # Add mock users
    combined.extend(mock_users)
    
    # Sort again by XP
    combined = sorted(combined, key=lambda x: x["xp"], reverse=True)
    
    # Assign ranks and take top 10
    final_leaderboard = []
    for i, user in enumerate(combined[:10]):
        user_data = user.copy()
        user_data["rank"] = i + 1
        user_data["avatar"] = None
        final_leaderboard.append(user_data)
        
    return final_leaderboard
