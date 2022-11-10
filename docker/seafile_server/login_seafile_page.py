#
# Copyright (C) 2022 Alexandre Mitsuru Kaihara
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#


from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver import FirefoxOptions
from selenium.webdriver.common.by import By

# Login informations
username = "alexandreamk1@gmail.com"
password = "Password123"

# Start Browser
opts = FirefoxOptions()
opts.add_argument("--headless")
print("Starting Firefox Browser on Headless mode")
browser = webdriver.Firefox(options=opts)

# Connect to the seafile login page
print("Connecting to the seafile login page")
browser.get('http://192.168.50.1:80')

# Fill Usersname field
print("Filling the username field with " + username )
search = browser.find_element(By.NAME, "login")
search.send_keys(username)
search.send_keys(Keys.RETURN)

# Fill password field
print("Filling the password field with " + password )
search = browser.find_element(By.NAME, "password")
search.send_keys(password)
search.send_keys(Keys.RETURN)

# Submit
print("Logging in ...")
search = browser.find_element(By.CLASS_NAME, "submit.btn.btn-primary.btn-block").click()

# Close Browser
print("Closing Browser\n\n")
browser.quit()