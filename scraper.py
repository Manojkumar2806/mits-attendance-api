from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import requests
import traceback

def scrape_attendance(reg_no, password):
    url = "http://mitsims.in/"

    def check_website_status(url):
        try:
            response = requests.get(url, timeout=10)
            return response.status_code == 200
        except requests.RequestException:
            return False

    options = Options()
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--allow-insecure-localhost')
    options.add_argument('--log-level=3')
    options.add_argument('--disable-software-rasterizer')
    options.add_argument('--remote-debugging-port=9222')

    # Set window size to avoid overlays and layout issues
    options.add_argument("--window-size=1920,1080")

    driver = None
    try:
        if not check_website_status(url):
            return {"error": "Website is down"}

        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.get(url)

        # Click the Student link (anchor tag)
        WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.ID, "studentLink"))).click()
        WebDriverWait(driver, 20).until(EC.visibility_of_element_located((By.ID, "studentForm")))

        form = driver.find_element(By.ID, "studentForm")
        form.find_element(By.ID, "inputStuId").send_keys(reg_no)
        form.find_element(By.ID, "inputPassword").send_keys(password)

        # Prepare to click submit button safely
        submit_button = form.find_element(By.ID, "studentSubmitButton")
        driver.execute_script("arguments[0].scrollIntoView(true);", submit_button)

        # Hide bottom navbar overlay if present to prevent click interception
        try:
            driver.execute_script("""
                var navbar = document.querySelector('.navbar-fixed-bottom');
                if (navbar) {
                    navbar.style.display = 'none';
                }
            """)
        except Exception:
            pass

        # Attempt normal click, fallback to JS click on interception
        try:
            submit_button.click()
        except Exception:
            driver.execute_script("arguments[0].click();", submit_button)

        # Check for login errors
        try:
            WebDriverWait(driver, 10).until(
                EC.any_of(
                    EC.presence_of_element_located((By.ID, "studentErrorDiv")),
                    EC.presence_of_element_located((By.CLASS_NAME, "x-form-display-field"))
                )
            )

            try:
                error_div = driver.find_element(By.ID, "studentErrorDiv")
                if error_div.is_displayed():
                    error_msg = error_div.text.strip().lower()
                    if error_msg:
                        return {"error": "Your Login Credentials are incorrect"}
                    else:
                        return {"error": "Your Login Credentials are incorrect"}
            except:
                pass

            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "x-form-display-field"))
            )

        except Exception as e:
            print(f"Error during login validation: {str(e)}")
            return {"error": "Your Login Credentials are incorrect"}

        # Scrape profile data
        fields = driver.find_elements(By.CLASS_NAME, "x-form-display-field")
        name = fields[0].text.strip() if fields else "Unknown"

        try:
            roll_number = driver.find_element(By.CSS_SELECTOR, "#profileUsn .x-form-display-field").text.strip()
        except Exception:
            roll_number = "Not Found"

        # Fix image URL
        try:
            image_element = driver.find_element(By.CSS_SELECTOR, ".x-component.profDetails img")  # Target <img> tag explicitly
            image_url = image_element.get_attribute("src")
            if not image_url or "loadImage.action" in image_url:
                image_url = "Image not found"  # Handle incomplete URLs
        except Exception:
            image_url = "Image not found"

        # Wait for attendance table to load
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".x-fieldset.bottom-border.x-fieldset-default"))
            )
        except Exception as e:
            print(f"Attendance table not found: {str(e)}")
            return {
                "name": name,
                "roll_number": roll_number,
                "total_classes": 0,
                "present": 0,
                "absent": 0,
                "percentage": 0,
                "subjects": {}
            }

        # Scrape attendance data
        attendance_rows = driver.find_elements(By.CSS_SELECTOR, ".x-fieldset.bottom-border.x-fieldset-default")
        subjects = {}
        total_present = 0
        total_conducted = 0

        for row in attendance_rows:
            try:
                subject_code = row.find_element(By.CSS_SELECTOR, "div.x-field.x-form-item:nth-child(2) .x-form-display-field").text.strip()
                present_text = row.find_element(By.CSS_SELECTOR, "div.x-field.x-form-item:nth-child(3) .x-form-display-field").text.strip()
                conducted_text = row.find_element(By.CSS_SELECTOR, "div.x-field.x-form-item:nth-child(4) .x-form-display-field").text.strip()

                present = int(present_text) if present_text else 0
                conducted = int(conducted_text) if conducted_text else 0

                absent = conducted - present

                subjects[subject_code] = {
                    "present": present,
                    "conducted": conducted,
                    "absent": absent
                }

                total_present += present
                total_conducted += conducted
            except Exception as e:
                print(f"❌ Error scraping row: {e}")
                traceback.print_exc()
                continue

        percentage = (total_present / total_conducted * 100) if total_conducted else 0

        return {
            "name": name,
            "roll_number": roll_number,
            "total_classes": total_conducted,
            "present": total_present,
            "absent": total_conducted - total_present,
            "percentage": round(percentage, 2),
            "subjects": subjects
        }

    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}

    finally:
        if driver:
            driver.quit()
