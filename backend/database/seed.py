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
                    # 50% chance of being late, 50% chance of being on time
                    is_late = random.random() < 0.50
                    
                    if is_late:
                        status = 'late'
                        # Lateness categories based on attendance_policy.md:
                        # Ringan (1-15 min): 60% chance
                        # Sedang (16-30 min): 25% chance
                        # Berat (> 30 min): 15% chance
                        late_type = random.random()
                        if late_type < 0.60:
                            check_in_hour = 8
                            check_in_min = random.randint(1, 15)
                            notes = f"Terlambat Ringan ({check_in_min} menit)"
                        elif late_type < 0.85:
                            check_in_hour = 8
                            check_in_min = random.randint(16, 30)
                            notes = f"Terlambat Sedang ({check_in_min} menit)"
                        else:
                            # 31 to 90 minutes late
                            late_minutes = random.randint(31, 90)
                            check_in_hour = 8 + (late_minutes // 60)
                            check_in_min = late_minutes % 60
                            notes = f"Terlambat Berat ({late_minutes} menit)"
                    else:
                        status = 'present'
                        # On time check-in (07:00 - 08:00)
                        check_in_hour = 7
                        check_in_min = random.randint(0, 59)
                        if random.random() < 0.1:
                            check_in_hour = 8
                            check_in_min = 0
                        notes = None
                    
                    check_in = datetime.combine(current_date, datetime.min.time().replace(hour=check_in_hour, minute=check_in_min))
                    
                    check_out_hour = random.randint(17, 19)
                    check_out_min = random.randint(0, 59)
                    check_out = datetime.combine(current_date, datetime.min.time().replace(hour=check_out_hour, minute=check_out_min))
                    
                    work_location = random.choice(work_locations)
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

def seed_payroll_slips(conn):
    """Create sample monthly payroll slips for last 3 months"""
    cur = conn.cursor()
    print("   Seeding Payroll Slips...")
    try:
        cur.execute("SELECT id, basic_salary, name FROM employees WHERE status = 'active'")
        employees = cur.fetchall()
        
        if not employees:
            print("      . Skipping payroll: no employees found.")
            return
        
        # Get HR user for generated_by
        cur.execute("SELECT id FROM hr_users WHERE role = 'admin'")
        admin_row = cur.fetchone()
        admin_id = admin_row[0] if admin_row else None
        
        today = date.today()
        count = 0
        
        # Generate payroll for last 3 months
        for months_ago in range(1, 4):
            m = today.month - months_ago
            y = today.year
            if m <= 0:
                m += 12
                y -= 1
            
            for emp_id, basic_salary, emp_name in employees:
                # Check existing
                cur.execute("""
                    SELECT id FROM payroll_slips 
                    WHERE employee_id = :emp_id AND period_month = :m AND period_year = :y
                """, {"emp_id": emp_id, "m": m, "y": y})
                if cur.fetchone():
                    continue
                
                salary = basic_salary or 5000000
                
                # Randomized components based on salary tier
                overtime = random.randint(0, 5) * 100000 if random.random() < 0.4 else 0
                bonus = random.choice([0, 0, 0, 500000, 1000000, 1500000]) if months_ago == 1 else 0
                
                # Allowances (proportional to salary)
                allow_transport = 500000 if salary < 10000000 else 750000
                allow_meal = 600000
                allow_housing = round(salary * 0.1) if salary >= 15000000 else 0
                allow_comm = 200000 if salary >= 10000000 else 100000
                allow_other = random.choice([0, 0, 150000, 250000])
                
                gross = salary + overtime + bonus + allow_transport + allow_meal + allow_housing + allow_comm + allow_other
                
                # Deductions
                ded_bpjs_kes = round(salary * 0.01)  # 1% employee portion
                ded_bpjs_tk = round(salary * 0.02)   # 2% employee portion
                ded_pph21 = round(salary * 0.05) if salary >= 10000000 else round(salary * 0.025)
                ded_loan = random.choice([0, 0, 0, 0, 500000, 1000000])
                ded_absence = random.choice([0, 0, 0, 100000, 200000])
                ded_other = 0
                
                total_ded = ded_bpjs_kes + ded_bpjs_tk + ded_pph21 + ded_loan + ded_absence + ded_other
                net = gross - total_ded
                
                payment_day = random.randint(25, 28)
                try:
                    payment_dt = date(y, m, payment_day)
                except ValueError:
                    payment_dt = date(y, m, 25)
                
                banks = ['BCA', 'BNI', 'Mandiri', 'BRI', 'CIMB Niaga']
                
                cur.execute("""
                    INSERT INTO payroll_slips (
                        employee_id, period_month, period_year,
                        basic_salary, overtime_pay, bonus,
                        allowance_transport, allowance_meal, allowance_housing,
                        allowance_communication, allowance_other,
                        deduction_bpjs_kesehatan, deduction_bpjs_ketenagakerjaan,
                        deduction_pph21, deduction_loan, deduction_absence, deduction_other,
                        gross_salary, total_deductions, net_salary,
                        payment_date, payment_method, bank_account,
                        status, generated_by
                    ) VALUES (
                        :emp_id, :m, :y,
                        :basic, :overtime, :bonus,
                        :at, :am, :ah, :ac, :ao,
                        :dbk, :dbt, :dp, :dl, :da, :do_,
                        :gross, :total_ded, :net,
                        :pay_date, :pay_method, :bank_acc,
                        :status, :gen_by
                    )
                """, {
                    "emp_id": emp_id, "m": m, "y": y,
                    "basic": salary, "overtime": overtime, "bonus": bonus,
                    "at": allow_transport, "am": allow_meal, "ah": allow_housing,
                    "ac": allow_comm, "ao": allow_other,
                    "dbk": ded_bpjs_kes, "dbt": ded_bpjs_tk,
                    "dp": ded_pph21, "dl": ded_loan, "da": ded_absence, "do_": ded_other,
                    "gross": gross, "total_ded": total_ded, "net": net,
                    "pay_date": payment_dt, "pay_method": "Transfer Bank",
                    "bank_acc": random.choice(banks),
                    "status": "finalized", "gen_by": admin_id
                })
                count += 1
        
        conn.commit()
        print(f"      + Created {count} payroll slip records.")
    except Exception as e:
        print(f"      x Error seeding payroll: {e}")
    finally:
        cur.close()


def seed_employee_cv(conn):
    """Create sample employee CV / profile data with deductions"""
    cur = conn.cursor()
    print("   Seeding Employee CVs...")
    try:
        cur.execute("SELECT id, name, department, position, basic_salary, bpjs_number FROM employees WHERE status = 'active'")
        employees = cur.fetchall()
        
        if not employees:
            print("      . Skipping CVs: no employees found.")
            return
        
        # Get HR user
        cur.execute("SELECT id FROM hr_users WHERE role = 'admin'")
        admin_row = cur.fetchone()
        admin_id = admin_row[0] if admin_row else None
        
        # Detailed CV data per employee code (matched by order of seed_employees)
        cv_details = [
            # EMP001 - Budi Santoso, IT, Software Engineer, 15M
            {"edu": "S1", "inst": "Universitas Indonesia", "major": "Teknik Informatika", "grad": 2018,
             "certs": "AWS Certified Developer, Oracle Certified Java Programmer",
             "skills": "Java, Python, React, PostgreSQL, Docker, AWS",
             "exp": "2018-2020: Junior Developer di PT Telkom\n2020-2023: Mid Developer di Tokopedia\n2023-sekarang: Software Engineer",
             "ec_name": "Yuni Santoso", "ec_phone": "08561234501", "ec_rel": "Istri",
             "blood": "O", "religion": "Islam", "ktp": "3175012345670001", "npwp": "12.345.678.9-012.000",
             "bank": "BCA", "bank_no": "1234567890", "bank_name": "Budi Santoso",
             "ded_meal": 0, "ded_transport": 0, "ded_insurance": 200000, "ded_laptop": 500000, "ded_laptop_mo": 18, "ded_other": 0, "ded_desc": ""},
            # EMP002 - Dewi Lestari, IT, DevOps Engineer, 18M
            {"edu": "S2", "inst": "Institut Teknologi Bandung", "major": "Teknik Komputer", "grad": 2017,
             "certs": "CKAD (Kubernetes), Terraform Associate, GCP Professional",
             "skills": "Kubernetes, Terraform, CI/CD, Linux, GCP, Azure, Monitoring",
             "exp": "2017-2019: System Admin di Bukalapak\n2019-2022: DevOps Engineer di Gojek\n2022-sekarang: DevOps Engineer",
             "ec_name": "Susi Lestari", "ec_phone": "08561234502", "ec_rel": "Ibu",
             "blood": "A", "religion": "Kristen", "ktp": "3175012345670002", "npwp": "12.345.678.9-013.000",
             "bank": "Mandiri", "bank_no": "1234567891", "bank_name": "Dewi Lestari",
             "ded_meal": 0, "ded_transport": 0, "ded_insurance": 300000, "ded_laptop": 750000, "ded_laptop_mo": 12, "ded_other": 0, "ded_desc": ""},
            # EMP003 - Andi Wijaya, IT, Data Analyst, 12M
            {"edu": "S1", "inst": "Universitas Gadjah Mada", "major": "Statistika", "grad": 2021,
             "certs": "Google Data Analytics Professional Certificate",
             "skills": "Python, SQL, Tableau, Power BI, Excel, R",
             "exp": "2021-2023: Data Intern di Shopee\n2023-sekarang: Data Analyst (contract)",
             "ec_name": "Darto Wijaya", "ec_phone": "08561234503", "ec_rel": "Ayah",
             "blood": "B", "religion": "Islam", "ktp": "3175012345670003", "npwp": "12.345.678.9-014.000",
             "bank": "BNI", "bank_no": "1234567892", "bank_name": "Andi Wijaya",
             "ded_meal": 50000, "ded_transport": 100000, "ded_insurance": 0, "ded_laptop": 0, "ded_laptop_mo": 0, "ded_other": 0, "ded_desc": ""},
            # EMP004 - Siti Rahayu, HR, HR Officer, 9M
            {"edu": "S1", "inst": "Universitas Airlangga", "major": "Psikologi", "grad": 2019,
             "certs": "CHRP (Certified Human Resources Professional)",
             "skills": "Rekrutmen, Payroll, HRIS, Regulasi Ketenagakerjaan, MS Office",
             "exp": "2019-2021: HR Admin di PT Astra\n2021-sekarang: HR Officer",
             "ec_name": "Ahmad Rahayu", "ec_phone": "08561234504", "ec_rel": "Suami",
             "blood": "AB", "religion": "Islam", "ktp": "3175012345670004", "npwp": "12.345.678.9-015.000",
             "bank": "BRI", "bank_no": "1234567893", "bank_name": "Siti Rahayu",
             "ded_meal": 50000, "ded_transport": 75000, "ded_insurance": 100000, "ded_laptop": 0, "ded_laptop_mo": 0, "ded_other": 0, "ded_desc": ""},
            # EMP005 - Rudi Hermawan, HR, Recruiter, 8.5M
            {"edu": "S1", "inst": "Universitas Padjadjaran", "major": "Manajemen SDM", "grad": 2022,
             "certs": "LinkedIn Recruiter Certification",
             "skills": "Talent Acquisition, Interview, LinkedIn Recruiting, Employer Branding",
             "exp": "2022-2023: Recruitment Intern di Unilever\n2023-sekarang: Recruiter (contract)",
             "ec_name": "Maria Hermawan", "ec_phone": "08561234505", "ec_rel": "Ibu",
             "blood": "O", "religion": "Katolik", "ktp": "3175012345670005", "npwp": "12.345.678.9-016.000",
             "bank": "BCA", "bank_no": "1234567894", "bank_name": "Rudi Hermawan",
             "ded_meal": 50000, "ded_transport": 75000, "ded_insurance": 0, "ded_laptop": 400000, "ded_laptop_mo": 6, "ded_other": 0, "ded_desc": ""},
            # EMP006 - Maya Putri, Finance, Accountant, 11M
            {"edu": "S1", "inst": "Universitas Trisakti", "major": "Akuntansi", "grad": 2018,
             "certs": "Brevet Pajak A & B, SAP Certified",
             "skills": "Akuntansi, Perpajakan, SAP, Excel Advanced, Financial Reporting",
             "exp": "2018-2020: Staff Accounting di Deloitte\n2020-2022: Senior Accountant di PwC\n2022-sekarang: Accountant",
             "ec_name": "Roni Putro", "ec_phone": "08561234506", "ec_rel": "Suami",
             "blood": "A", "religion": "Islam", "ktp": "3175012345670006", "npwp": "12.345.678.9-017.000",
             "bank": "Mandiri", "bank_no": "1234567895", "bank_name": "Maya Putri",
             "ded_meal": 0, "ded_transport": 0, "ded_insurance": 150000, "ded_laptop": 0, "ded_laptop_mo": 0, "ded_other": 100000, "ded_desc": "Parkir bulanan"},
            # EMP007 - Agus Prasetyo, Finance, Financial Analyst, 13M
            {"edu": "S2", "inst": "Universitas Indonesia", "major": "Magister Manajemen Keuangan", "grad": 2019,
             "certs": "CFA Level 2, FRM Part 1",
             "skills": "Financial Modeling, Valuation, Bloomberg Terminal, Python, Excel VBA",
             "exp": "2019-2021: Financial Analyst di JP Morgan\n2021-2023: Senior Analyst di Bank Mandiri\n2023-sekarang: Financial Analyst",
             "ec_name": "Lina Prasetyo", "ec_phone": "08561234507", "ec_rel": "Ibu",
             "blood": "B", "religion": "Islam", "ktp": "3175012345670007", "npwp": "12.345.678.9-018.000",
             "bank": "CIMB Niaga", "bank_no": "1234567896", "bank_name": "Agus Prasetyo",
             "ded_meal": 0, "ded_transport": 0, "ded_insurance": 250000, "ded_laptop": 600000, "ded_laptop_mo": 10, "ded_other": 0, "ded_desc": ""},
            # EMP008 - Linda Kartika, Marketing, Marketing Executive, 10M
            {"edu": "S1", "inst": "London School of PR", "major": "Komunikasi & PR", "grad": 2020,
             "certs": "Google Ads Certification, HubSpot Inbound Marketing",
             "skills": "Digital Marketing, SEO/SEM, Social Media, Content Strategy, Google Analytics",
             "exp": "2020-2022: Marketing Associate di Grab\n2022-sekarang: Marketing Executive",
             "ec_name": "Kartika Dewi", "ec_phone": "08561234508", "ec_rel": "Ibu",
             "blood": "O", "religion": "Hindu", "ktp": "3175012345670008", "npwp": "12.345.678.9-019.000",
             "bank": "BCA", "bank_no": "1234567897", "bank_name": "Linda Kartika",
             "ded_meal": 0, "ded_transport": 100000, "ded_insurance": 150000, "ded_laptop": 500000, "ded_laptop_mo": 15, "ded_other": 0, "ded_desc": ""},
            # EMP009 - Fajar Nugroho, Marketing, Content Writer, 7.5M
            {"edu": "S1", "inst": "Universitas Diponegoro", "major": "Sastra Inggris", "grad": 2021,
             "certs": "Content Marketing Institute Certification",
             "skills": "Copywriting, SEO Writing, WordPress, Canva, Adobe InDesign",
             "exp": "2021-2022: Freelance Writer\n2022-sekarang: Content Writer (contract)",
             "ec_name": "Sri Nugroho", "ec_phone": "08561234509", "ec_rel": "Istri",
             "blood": "AB", "religion": "Islam", "ktp": "3175012345670009", "npwp": "12.345.678.9-020.000",
             "bank": "BNI", "bank_no": "1234567898", "bank_name": "Fajar Nugroho",
             "ded_meal": 50000, "ded_transport": 100000, "ded_insurance": 0, "ded_laptop": 0, "ded_laptop_mo": 0, "ded_other": 0, "ded_desc": ""},
            # EMP010 - Hendra Kusuma, Operations, Operations Manager, 25M
            {"edu": "S2", "inst": "Universitas Indonesia", "major": "Magister Teknik Industri", "grad": 2014,
             "certs": "PMP (Project Management Professional), Lean Six Sigma Black Belt",
             "skills": "Operations Management, Supply Chain, Lean, Project Management, ERP (SAP)",
             "exp": "2014-2017: Production Supervisor di Unilever\n2017-2020: Operations Lead di Danone\n2020-sekarang: Operations Manager",
             "ec_name": "Rina Kusuma", "ec_phone": "08561234510", "ec_rel": "Istri",
             "blood": "A", "religion": "Kristen", "ktp": "3175012345670010", "npwp": "12.345.678.9-021.000",
             "bank": "BCA", "bank_no": "1234567899", "bank_name": "Hendra Kusuma",
             "ded_meal": 0, "ded_transport": 0, "ded_insurance": 500000, "ded_laptop": 0, "ded_laptop_mo": 0, "ded_other": 200000, "ded_desc": "Keanggotaan gym kantor"},
            # EMP011 - Ratna Sari, Sales, Sales Executive, 6.5M
            {"edu": "D3", "inst": "Politeknik Negeri Jakarta", "major": "Administrasi Bisnis", "grad": 2023,
             "certs": "Salesforce Administrator",
             "skills": "Sales, Negotiation, CRM, Presentation, Customer Relations",
             "exp": "2023-sekarang: Sales Executive (contract)",
             "ec_name": "Bambang Sari", "ec_phone": "08561234511", "ec_rel": "Ayah",
             "blood": "B", "religion": "Islam", "ktp": "3175012345670011", "npwp": "12.345.678.9-022.000",
             "bank": "BRI", "bank_no": "1234567900", "bank_name": "Ratna Sari",
             "ded_meal": 50000, "ded_transport": 100000, "ded_insurance": 0, "ded_laptop": 350000, "ded_laptop_mo": 8, "ded_other": 0, "ded_desc": ""},
            # EMP012 - Dimas Pratama, Sales, Account Manager, 20M
            {"edu": "S1", "inst": "Prasetiya Mulya Business School", "major": "Business Administration", "grad": 2016,
             "certs": "Certified Sales Professional (CSP), Google Analytics",
             "skills": "Account Management, B2B Sales, Strategic Planning, Client Relations, Negotiation",
             "exp": "2016-2018: Sales Rep di Microsoft Indonesia\n2018-2021: Senior Account Exec di Oracle\n2021-sekarang: Account Manager",
             "ec_name": "Putri Amelia", "ec_phone": "08561234512", "ec_rel": "Mantan Istri (Wali Anak)",
             "blood": "O", "religion": "Islam", "ktp": "3175012345670012", "npwp": "12.345.678.9-023.000",
             "bank": "Mandiri", "bank_no": "1234567901", "bank_name": "Dimas Pratama",
             "ded_meal": 0, "ded_transport": 0, "ded_insurance": 400000, "ded_laptop": 0, "ded_laptop_mo": 0, "ded_other": 150000, "ded_desc": "Asuransi anak"},
        ]
        
        count = 0
        for i, (emp_id, emp_name, dept, pos, salary, bpjs) in enumerate(employees):
            # Check existing
            cur.execute("SELECT id FROM employee_cv WHERE employee_id = :emp_id", {"emp_id": emp_id})
            if cur.fetchone():
                print(f"      . CV already exists: {emp_name}")
                continue
            
            # Use matching detail if available, otherwise generate generic
            if i < len(cv_details):
                d = cv_details[i]
            else:
                d = cv_details[0]  # fallback
            
            salary = salary or 5000000
            ded_bpjs_kes = round(salary * 0.01)
            ded_bpjs_tk = round(salary * 0.02)
            total_ded = ded_bpjs_kes + ded_bpjs_tk + d["ded_meal"] + d["ded_transport"] + d["ded_insurance"] + d["ded_laptop"] + d["ded_other"]
            
            cur.execute("""
                INSERT INTO employee_cv (
                    employee_id, current_position, current_department, current_salary,
                    education_level, education_institution, education_major, graduation_year,
                    certifications, skills, work_experience,
                    emergency_contact_name, emergency_contact_phone, emergency_contact_relation,
                    blood_type, religion, ktp_number, npwp_number,
                    bank_name, bank_account_number, bank_account_name,
                    deduction_bpjs_kesehatan, deduction_bpjs_ketenagakerjaan,
                    deduction_meal, deduction_transport, deduction_insurance,
                    deduction_laptop_installment, deduction_laptop_remaining_months,
                    deduction_other, deduction_other_description,
                    total_monthly_deductions,
                    last_updated_by
                ) VALUES (
                    :emp_id, :pos, :dept, :salary,
                    :edu, :inst, :major, :grad,
                    :certs, :skills, :exp,
                    :ec_name, :ec_phone, :ec_rel,
                    :blood, :religion, :ktp, :npwp,
                    :bank, :bank_no, :bank_name,
                    :dbk, :dbt,
                    :dm, :dt, :di,
                    :dl, :dlm,
                    :do_, :dd,
                    :total_ded,
                    :updated_by
                )
            """, {
                "emp_id": emp_id, "pos": pos, "dept": dept, "salary": salary,
                "edu": d["edu"], "inst": d["inst"], "major": d["major"], "grad": d["grad"],
                "certs": d["certs"], "skills": d["skills"], "exp": d["exp"],
                "ec_name": d["ec_name"], "ec_phone": d["ec_phone"], "ec_rel": d["ec_rel"],
                "blood": d["blood"], "religion": d["religion"], "ktp": d["ktp"], "npwp": d["npwp"],
                "bank": d["bank"], "bank_no": d["bank_no"], "bank_name": d["bank_name"],
                "dbk": ded_bpjs_kes, "dbt": ded_bpjs_tk,
                "dm": d["ded_meal"], "dt": d["ded_transport"], "di": d["ded_insurance"],
                "dl": d["ded_laptop"], "dlm": d["ded_laptop_mo"],
                "do_": d["ded_other"], "dd": d["ded_desc"],
                "total_ded": total_ded,
                "updated_by": admin_id
            })
            count += 1
            print(f"      + Created CV for {emp_name}")
        
        conn.commit()
        print(f"      + Created {count} employee CV records.")
    except Exception as e:
        print(f"      x Error seeding CVs: {e}")
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
        seed_payroll_slips(conn)
        seed_employee_cv(conn)
    except Exception as e:
        print(f"Global seed error: {e}")
    finally:
        conn.close()
    
    print("\n" + "=" * 50)
    print("Database seeding completed.")
    print("=" * 50)

if __name__ == "__main__":
    seed_all()
