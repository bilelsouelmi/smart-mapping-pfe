import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import csv
import json
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.standard_element import StandardElement

def import_standard_elements(csv_path: str, db: Session):
    """Import standard elements from CSV"""
    print(f"📥 Importing standard elements from {csv_path}...")
    
    count = 0
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Parse JSON fields
            tags = None
            if row.get('tags'):
                try:
                    tags = json.loads(row['tags'])
                except:
                    tags = None
            
            # Convert boolean
            is_required = row.get('is_required', '').lower() == 'true'
            
            element = StandardElement(
                element_id=row['element_id'],
                element_name=row['element_name'],
                category=row['category'],
                business_domain=row['business_domain'],
                source_path=row.get('source_path') or None,
                target_path=row.get('target_path') or None,
                iso20022_path=row.get('iso20022_path') or None,
                data_type=row['data_type'],
                description=row.get('description') or None,
                example_value=row.get('example_value') or None,
                is_required=is_required,
                tags=tags,
                is_active=True
            )
            
            db.add(element)
            count += 1
    
    db.commit()
    print(f"✅ Imported {count} standard elements")

def main():
    db = SessionLocal()
    
    try:
        # Import standard elements
        csv_file = os.path.join(
            os.path.dirname(__file__), 
            '../dataset/standard_elements_pain001.csv'
        )
        
        if os.path.exists(csv_file):
            import_standard_elements(csv_file, db)
        else:
            print(f"❌ File not found: {csv_file}")
            print(f"Current directory: {os.getcwd()}")
            print(f"Script directory: {os.path.dirname(__file__)}")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    main()