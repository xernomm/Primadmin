import os
import cx_Oracle
import bcrypt
import random
from datetime import date, datetime, timedelta
from database.db import get_connection

def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def seed_hr_users(conn):
    """Create default HR users"""
    users = [
        {
            'username': 'admin',
            'email': 'admin@hr.com', # Changed from example to match our previous convention, or keep consistent? Let's use @hr.com for consistency or company.com from example. Example used company.com. I'll stick to @hr.com to match previous artifacts if any, but example is better. Let's use example's emails but ensure admin matches if I want to keep 'admin@hr.com'. Actually, let's use the example's specific data for richness.
            'password_hash': hash_password('admin123'),
            'full_name': 'Administrator',
            'role': 'admin'
        },
        {
            'username': 'hr_manager',
            'email': 'hr.manager@hr.com',
            'password_hash': hash_password('manager123'),
            'full_name': 'HR Manager',
            'role': 'hr_manager'
        },
        {
            'username': 'hr_staff',
            'email': 'hr.staff@hr.com',
            'password_hash': hash_password('staff123'),
            'full_name': 'HR Staff',
            'role': 'hr_staff'
        }
    ]
    
    cur = conn.cursor()
    print("   Seeding HR Users...")
    try:
        for user_data in users:
            cur.execute("SELECT id FROM hr_users WHERE username = :username", {"username": user_data['username']})
            if not cur.fetchone():
                cur.execute("""
                    INSERT INTO hr_users (username, email, password_hash, full_name, role)
                    VALUES (:username, :email, :password_hash, :full_name, :role)
                """, user_data)
                print(f"      + Created user: {user_data['username']}")
            else:
                print(f"      . User already exists: {user_data['username']}")
        conn.commit()
    except Exception as e:
        print(f"      x Error seeding users: {e}")
    finally:
        cur.close()

def seed_employees(conn):
    """Create sample employees"""
    employees_data = [
        # IT Department
        {'code': 'EMP001', 'name': 'Budi Santoso', 'email': 'budi.santoso@hr.com', 'phone': '08123456701', 'dept': 'IT', 'pos': 'Software Engineer', 
         'addr': 'Jl. Sudirman No. 123, Jakarta Selatan', 'status': 'married', 'salary': 15000000, 'bpjs': '12345678901', 'leave': 10, 'emp_status': 'permanent'},
        {'code': 'EMP002', 'name': 'Dewi Lestari', 'email': 'dewi.lestari@hr.com', 'phone': '08123456702', 'dept': 'IT', 'pos': 'DevOps Engineer',
         'addr': 'Jl. Gatot Subroto Kav. 5, Jakarta Selatan', 'status': 'single', 'salary': 18000000, 'bpjs': '12345678902', 'leave': 8, 'emp_status': 'permanent'},
        {'code': 'EMP003', 'name': 'Andi Wijaya', 'email': 'andi.wijaya@hr.com', 'phone': '08123456703', 'dept': 'IT', 'pos': 'Data Analyst',
         'addr': 'Komp. Gading Serpong, Tangerang', 'status': 'single', 'salary': 12000000, 'bpjs': '12345678903', 'leave': 12, 'emp_status': 'contract'},
        
        # HR Department
        {'code': 'EMP004', 'name': 'Siti Rahayu', 'email': 'siti.rahayu@hr.com', 'phone': '08123456704', 'dept': 'HR', 'pos': 'HR Officer',
         'addr': 'Jl. Kaliurang Km 5, Yogyakarta', 'status': 'married', 'salary': 9000000, 'bpjs': '12345678904', 'leave': 6, 'emp_status': 'permanent'},
        {'code': 'EMP005', 'name': 'Rudi Hermawan', 'email': 'rudi.hermawan@hr.com', 'phone': '08123456705', 'dept': 'HR', 'pos': 'Recruiter',
         'addr': 'Jl. Braga No. 10, Bandung', 'status': 'single', 'salary': 8500000, 'bpjs': '12345678905', 'leave': 11, 'emp_status': 'contract'},
        
        # Finance Department
        {'code': 'EMP006', 'name': 'Maya Putri', 'email': 'maya.putri@hr.com', 'phone': '08123456706', 'dept': 'Finance', 'pos': 'Accountant',
         'addr': 'Apartemen Mediterania, Jakarta Barat', 'status': 'married', 'salary': 11000000, 'bpjs': '12345678906', 'leave': 5, 'emp_status': 'permanent'},
        {'code': 'EMP007', 'name': 'Agus Prasetyo', 'email': 'agus.prasetyo@hr.com', 'phone': '08123456707', 'dept': 'Finance', 'pos': 'Financial Analyst',
         'addr': 'Jl. Raya Bogor Km 30, Depok', 'status': 'single', 'salary': 13000000, 'bpjs': '12345678907', 'leave': 12, 'emp_status': 'permanent'},
        
        # Marketing Department
        {'code': 'EMP008', 'name': 'Linda Kartika', 'email': 'linda.kartika@hr.com', 'phone': '08123456708', 'dept': 'Marketing', 'pos': 'Marketing Executive',
         'addr': 'Jl. Kemang Raya No. 88, Jakarta Selatan', 'status': 'single', 'salary': 10000000, 'bpjs': '12345678908', 'leave': 9, 'emp_status': 'permanent'},
        {'code': 'EMP009', 'name': 'Fajar Nugroho', 'email': 'fajar.nugroho@hr.com', 'phone': '08123456709', 'dept': 'Marketing', 'pos': 'Content Writer',
         'addr': 'Jl. Taman Siswa, Semarang', 'status': 'married', 'salary': 7500000, 'bpjs': '12345678909', 'leave': 12, 'emp_status': 'contract'},
        
        # Operations Department
        {'code': 'EMP010', 'name': 'Hendra Kusuma', 'email': 'hendra.kusuma@hr.com', 'phone': '08123456710', 'dept': 'Operations', 'pos': 'Operations Manager',
         'addr': 'Jl. Pemuda No. 45, Surabaya', 'status': 'married', 'salary': 25000000, 'bpjs': '12345678910', 'leave': 15, 'emp_status': 'permanent'},
        
        # Sales Department
        {'code': 'EMP011', 'name': 'Ratna Sari', 'email': 'ratna.sari@hr.com', 'phone': '08123456711', 'dept': 'Sales', 'pos': 'Sales Executive',
         'addr': 'Jl. Malioboro, Yogyakarta', 'status': 'single', 'salary': 6500000, 'bpjs': '12345678911', 'leave': 12, 'emp_status': 'contract'},
        {'code': 'EMP012', 'name': 'Dimas Pratama', 'email': 'dimas.pratama@hr.com', 'phone': '08123456712', 'dept': 'Sales', 'pos': 'Account Manager',
         'addr': 'Jl. MH Thamrin, Jakarta Pusat', 'status': 'divorced', 'salary': 20000000, 'bpjs': '12345678912', 'leave': 7, 'emp_status': 'permanent'},
    ]
    
    cur = conn.cursor()
    print("   Seeding Employees...")
    try:
        for emp_data in employees_data:
            cur.execute("SELECT id FROM employees WHERE employee_code = :code", {"code": emp_data['code']})
            if not cur.fetchone():
                # Random join date within last 3 years
                days_ago = random.randint(30, 1095)
                join_date = date.today() - timedelta(days=days_ago)
                
                cur.execute("""
                    INSERT INTO employees (
                        employee_code, name, email, phone, department, position, 
                        status, joined_at, address, marital_status, basic_salary, 
                        bpjs_number, remaining_leave, employment_status
                    ) VALUES (
                        :code, :name, :email, :phone, :dept, :pos, 
                        'active', :joined_at, :addr, :status, :salary, 
                        :bpjs, :leave, :emp_status
                    )
                """, {
                    'code': emp_data['code'],
                    'name': emp_data['name'],
                    'email': emp_data['email'],
                    'phone': emp_data['phone'],
                    'dept': emp_data['dept'],
                    'pos': emp_data['pos'],
                    'joined_at': join_date,
                    'addr': emp_data['addr'],
                    'status': emp_data['status'],
                    'salary': emp_data['salary'],
                    'bpjs': emp_data['bpjs'],
                    'leave': emp_data['leave'],
                    'emp_status': emp_data['emp_status']
                })
                print(f"      + Created employee: {emp_data['name']}")
            else:
                print(f"      . Employee already exists: {emp_data['code']}")
        conn.commit()
    except Exception as e:
        print(f"      x Error seeding employees: {e}")
    finally:
        cur.close()

def seed_attendance(conn):
    """Create sample attendance records for the current month"""
    work_locations = ['WFO', 'WFH', 'field']
    
    cur = conn.cursor()
    print("   Seeding Attendance...")
    try:
        cur.execute("SELECT id FROM employees WHERE status = 'active'")
        employees = [row[0] for row in cur.fetchall()]
        
        today = date.today()
        count = 0
        
        for days_ago in range(30):
            current_date = today - timedelta(days=days_ago)
            
            # Skip weekends
            if current_date.weekday() >= 5:
                continue
            
            for emp_id in employees:
                # Check for existing
                cur.execute("SELECT id FROM attendance WHERE employee_id = :emp_id AND attendance_date = :att_date", 
                           {"emp_id": emp_id, "att_date": current_date})
                if cur.fetchone():
                    continue
                
                rand_val = random.random()
                if rand_val < 0.90:
                    status = 'present'
                    check_in_hour = random.randint(7, 9)
                    check_in_min = random.randint(0, 59)
                    check_in = datetime.combine(current_date, datetime.min.time().replace(hour=check_in_hour, minute=check_in_min))
                    
                    check_out_hour = random.randint(17, 19)
                    check_out_min = random.randint(0, 59)
                    check_out = datetime.combine(current_date, datetime.min.time().replace(hour=check_out_hour, minute=check_out_min))
                    
                    work_location = random.choice(work_locations)
                    notes = None
                elif rand_val < 0.95:
                    status = 'sick'
                    check_in = None
                    check_out = None
                    work_location = 'WFH'
                    notes = "Sakit flu"
                else:
                    status = random.choice(['absent', 'leave'])
                    check_in = None
                    check_out = None
                    work_location = 'WFO'
                    notes = "Cuti tahunan" if status == 'leave' else "Tanpa keterangan"
                
                cur.execute("""
                    INSERT INTO attendance (
                        employee_id, attendance_date, check_in, check_out, 
                        work_location, status, notes
                    ) VALUES (
                        :emp_id, :att_date, :check_in, :check_out, 
                        :loc, :status, :notes
                    )
                """, {
                    "emp_id": emp_id,
                    "att_date": current_date,
                    "check_in": check_in,
                    "check_out": check_out,
                    "loc": work_location,
                    "status": status,
                    "notes": notes
                })
                count += 1
                
        conn.commit()
        print(f"      + Created {count} attendance records.")
    except Exception as e:
        print(f"      x Error seeding attendance: {e}")
    finally:
        cur.close()

def seed_warnings(conn):
    """Create sample warning letters"""
    warning_reasons = [
        "Terlambat masuk kerja lebih dari 3 kali dalam sebulan",
        "Tidak hadir tanpa keterangan",
        "Pelanggaran SOP perusahaan",
        "Kinerja tidak sesuai target"
    ]
    
    cur = conn.cursor()
    print("   Seeding Warnings...")
    try:
        # Get up to 3 active employees
        cur.execute("SELECT id, name FROM employees WHERE status = 'active' FETCH FIRST 3 ROWS ONLY")
        employees = cur.fetchall()
        
        # Get HR Manager
        cur.execute("SELECT id FROM hr_users WHERE role = 'hr_manager'")
        manager = cur.fetchone()
        
        if not employees or not manager:
            print("      . Skipping warnings: no employees or HR manager found.")
            return

        manager_id = manager[0]
        
        for emp in employees[:2]:
            emp_id = emp[0]
            cur.execute("SELECT id FROM warnings WHERE employee_id = :emp_id", {"emp_id": emp_id})
            if cur.fetchone():
                continue
                
            cur.execute("""
                INSERT INTO warnings (
                    employee_id, warning_type, reason, issued_date, 
                    issued_by, email_sent, email_sent_at
                ) VALUES (
                    :emp_id, 'SP1', :reason, :issued_date, 
                    :issued_by, 1, :sent_at
                )
            """, {
                "emp_id": emp_id,
                "reason": random.choice(warning_reasons),
                "issued_date": date.today() - timedelta(days=random.randint(10, 60)),
                "issued_by": manager_id,
                "sent_at": datetime.now() - timedelta(days=random.randint(10, 60))
            })
            print(f"      + Created warning for {emp[1]}")
            
        conn.commit()
    except Exception as e:
        print(f"      x Error seeding warnings: {e}")
    finally:
        cur.close()

def seed_all():
    print("\n" + "=" * 50)
    print("Starting database seeding...")
    print("=" * 50)
    
    conn = get_connection()
    try:
        seed_hr_users(conn)
        seed_employees(conn)
        seed_attendance(conn)
        seed_warnings(conn)
    except Exception as e:
        print(f"Global seed error: {e}")
    finally:
        conn.close()
    
    print("\n" + "=" * 50)
    print("Database seeding completed.")
    print("=" * 50)

if __name__ == "__main__":
    seed_all()
