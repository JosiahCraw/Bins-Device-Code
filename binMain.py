import RPi.GPIO as GPIO
import time
import board
import neopixel
import math
import random
import string
import signal
import os
import threading
import ledPatterns

# FireBase Python
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
from firebase_admin import storage
import google.cloud.exceptions

from luma.core.interface.serial import i2c
from luma.core.render import canvas
from luma.oled.device import ssd1306, ssd1325, ssd1331, sh1106
from PIL import ImageFont, ImageDraw, Image

serial = i2c(port=1, address=0x3C)
device = ssd1306(serial, rotate=0)

GPIO.setmode(GPIO.BCM)


IR1 = 5
IR2 = 6
IR3 = 13
IR4 = 19

TRIG = 23
ECHO = 24

GPIO.setup(TRIG,GPIO.OUT)
GPIO.setup(ECHO,GPIO.IN)

GPIO.setup(IR1,GPIO.IN)
GPIO.setup(IR2,GPIO.IN)
GPIO.setup(IR3,GPIO.IN)
GPIO.setup(IR4,GPIO.IN)

pixels = neopixel.NeoPixel(board.D18, 100,auto_write = False)


global rubbishDetected
rubbishDetected = 0
active = True
userActive = False
user = ""
timeLoggedIn = 0
imageName = ""
imageChanged = True


# Setting signal handler to handle SIGINT for safe shutdown


def receiveSigInt(signalNumber, frame):
    print('SIGINT received, exiting')
    global active
    active = False


# FireBase Inits
# @params None
# @returns FirestoreClient db, String binId
# --This function reads the settings.conf file and if a Firebase document exists for that ID
# --the program will continue other wise an empty document is created with DocumentReference
# --of the ID, the user data from the field is always cleared to ensure no user is left active


def initFirebase():
    cred = credentials.Certificate('bins-5653b-firebase-adminsdk-w6hyh-33c31c1ceb.json')
    firebase_admin.initialize_app(cred, {'storageBucket': 'bins-5653b.appspot.com'})
    db = firestore.client()
    bucket = storage.bucket()

    confFile = open("settings.conf", "r")
    if confFile.mode == 'r':
        contents = confFile.readlines()
        print(contents)
        id = contents[0].split(':')[1].strip()
        print(id)

    try:
        binRef = db.collection(u'bins').document(id).get()
    except google.cloud.exceptions.NotFound:
        print(u'Cloud Failed')

    if not binRef.exists:
        print(u'Document for Bin ID doesnt not exist')
        name = contents[1].split(':')[1]
        location = contents[2].split(':')[1]

        print(name)
        print(location)
        id.strip()
        db.collection(u'bins').document(id).create({
            u'full': False,
            u'location': location,
            u'name': name,
            u'tempCode': u'',
            u'userActive': u'',
            u'image': u'PacMan.jpg'
            })
    confFile.close()

    db.collection(u'bins').document(id).update({'userActive': ''})

    return db, id, bucket


# FireBase Code

# getUser()
# @params FirestoreClient db, String binId
# @returns String user (User UID)
# --Get user does a get request to the database and return either the active users UID or None


def getUser(db, binId):
    try:
        bins = db.collection(u'bins').document(binId).get()
    except google.cloud.exceptions.NotFound:
        print(u'Failed To get Bins data')

    binDict = bins.to_dict()

    print(bins)

    try:
        user = binDict["userActive"]
    except TypeError:
        print(u'User bad type:')
        print(user)

    print(user)

    return user


def onDocChange(doc_snapshot, changes, read_time):
    doc = doc_snapshot
    print('Bins changed')
    docSnapshot = doc[0]
    data = docSnapshot.to_dict()
    updatedUser = data["userActive"]
    image = data["image"]
    global user
    global userActive
    if updatedUser != "":
        if user != updatedUser:
            user = updatedUser
            print("Updated there is a new User")
            userActive = True
            global timeLoggedIn
            timeLoggedIn = time.time()
    else:
        print("Updated there is no user :(")
        userActive = False
    global imageName
    print(image)
    if image != imageName:
        global imageChanged
        imageChanged = True
        imageName = image


# userConnectSnapCreate()
# @params FirestoreClient db, String binId
# @returns DocumentSnapshot docSnap
# --This function is currently unused but may be helpful as it reads and changes on the bin document
# --this function may be return to use as the current method of using getUser every time a item is put in the
# --bin is inefficient


def userConnectSnapCreate(db, binId):
    doc = db.collection(u'bins').document(binId)
    docSnap = doc.on_snapshot(onDocChange)
    return docSnap

# putCodeToDatabase()
# @params FirestoreClient db, String code, String binId
# --This function updates the tempCode field of the database to include the given code


def putCodeToDatabase(db, code, binId):
    print(binId)
    db.collection(u'bins').document(binId).update({u'tempCode': code, u'userActive': u''})

# createCode()
# @returns String code
# --This function returns two random letters followed by two random numbers in a string


def createCode():
    randLetters = random.choice(string.ascii_uppercase)
    randLetters += random.choice(string.ascii_uppercase)
    randLetters += str(random.randint(10, 99))

    print('New Code: ' + randLetters)
    return randLetters

# incrementCount()
# @params FirestoreClient db, String binId
# --This function takes the database and the binId and gets the current user then increments the count field of that
# --user by one in the database


def incrementCount(db, binId):
        print(binId)

        user = getUser(db, binId)

        if user == '':
            print(u'No Active User')
            return
        else:
            userDoc = db.collection(u'Users').document(user)

            userData = userDoc.get()
            userDict = userData.to_dict()

            newCount = userDict['Count'] + 1
            userDoc.update({u'Count': newCount})

# removeBinDoc()
# @params FirestoreClient db, String binId
# --This function is part of the cleanup routine on close it removes the bin document in the database when it is
# --called


def removeBinDoc(db, binId):
    print('Removing Bin Doc')
    db.collection(u'bins').document(binId).delete()


def setBinFull(db, binId, isFull):
    print("Is full: " + str(isFull))
    db.collection(u'bins').document(binId).update({u'full': isFull})


def rubbishDetectedInterrupt(channel):
    global rubbishDetected
    print("Sensor Triggered")
    rubbishDetected = 1
    print("Rubbish Detected")


def displayUniqueID(uniqueID):
    # Box and text rendered in portrait mode
    with canvas(device) as draw:
        font = ImageFont.truetype('Oswald-Regular.ttf',45)
        draw.rectangle(device.bounding_box, outline="white", fill="black")
        draw.text((0, 5), str(uniqueID),font=font, fill="white")
    

def ledRubbishDetectedChase():
    global rubbishDetected
    number = random.randint(1,3)
    if number == 1:
        ledPatterns.LEDRainbowChase(pixels,0.02)
    elif number == 2:
        ledPatterns.LEDTetrisChase(pixels,0.2)
    else:
        ledPatterns.LEDSnakeChase(pixels,0.2)
   # for i in range(0,100):
   #     pixels[i] = (255, 0, 0)
   # pixels.show()
   # time.sleep(5)
    
    
    
    global imageName
    imagify(imageName)
    rubbishDetected = 0


def ledAdvertising():
    for i in range(0,100):
        pixels[i] = (0, 0, 255)
    pixels.show()
    time.sleep(1)


def getImageName(db, binId):
    doc = db.collection(u'bins').document(binId).get()
    docDict = doc.to_dict()
    image = docDict["image"]
    print(image)
    return image


def downloadImage(bucket, image):
    blob = bucket.blob(image)
    blob.download_to_filename(image)
    print(image + " Downloaded!")
    global imageName
    if image is not imageName:
        os.remove(imageName)
    print("Removed " + imageName)
    imageName = image
    print("New image set! " + imageName)


def measureBinLevel():
    GPIO.output(TRIG, False)
    print("Waiting For Sensor To Settle")
    time.sleep(2)
    print("Measuring Bin Level")
    GPIO.output(TRIG,True)
    time.sleep(0.00008)
    GPIO.output(TRIG,False)

    while(GPIO.input(ECHO) == 0):
        pulse_start = time.time()
    while(GPIO.input(ECHO) == 1):
        pulse_end = time.time()
        pulse_duration = pulse_end - pulse_start
    distance = pulse_duration * 17150 #Speed of sound / 2 343ms
    distance = round(distance,2)
    print("Bin Space Left:",distance,"cm")
    return distance


def imagify(file_path):
    im = Image.open(file_path)
    width, height = im.size
    pix = im.load()
    #print("Image opened")
    colour_list = []
    for x in range(10):
        for i in range(0,10):
            new_colour = pix[int((width/10)*i),int((height/10)*x)]
            colour_list.append(new_colour)
            LED_Number = i+(10*x)
            pixels[LED_Number] = ((new_colour));
    pixels.show()
        

GPIO.add_event_detect(IR1, GPIO.RISING, callback=rubbishDetectedInterrupt, bouncetime=300)
GPIO.add_event_detect(IR2, GPIO.RISING, callback=rubbishDetectedInterrupt, bouncetime=300)
GPIO.add_event_detect(IR3, GPIO.RISING, callback=rubbishDetectedInterrupt, bouncetime=300)
GPIO.add_event_detect(IR4, GPIO.RISING, callback=rubbishDetectedInterrupt, bouncetime=300)


def main():
    global rubbishDetected
    signal.signal(signal.SIGINT, receiveSigInt)
    db, binId, bucket = initFirebase()
    docSnap = userConnectSnapCreate(db, binId)
    code = createCode()
    putCodeToDatabase(db, code, binId)
    print(binId)
    global active
    global imageName
    global timeLoggedIn
    imageName = getImageName(db, binId)
    while(active):
        if userActive:
            currentTime = time.time()
            elapsedTime = currentTime - timeLoggedIn
            print(elapsedTime)
            if elapsedTime > 30:
                elapsedTime = 30
            displayUniqueID(str(math.floor(elapsedTime)))
            if elapsedTime >= 30:
                displayUniqueID("Closed")
                time.sleep(2)
                code = createCode()
                putCodeToDatabase(db, code, binId)
        else:
            displayUniqueID(code)

        if rubbishDetected == 1:
            incrementCount(db, binId)
            ledRubbishDetectedChase()
            distance = measureBinLevel()
            if distance < 10:
                setBinFull(db, binId, True)
            else:
                setBinFull(db, binId, False)
        else:
            global imageChanged
            if imageChanged:
                downloadImage(bucket, imageName)
                imageChanged = False
                imagify(imageName)
        time.sleep(1)

    #GPIO.cleanup()
    global pixels
    pixels.fill((0,0,0))
    putCodeToDatabase(db, "Empty", binId)
    removeBinDoc(db, binId)
    os.remove(imageName)
    return 1


main()




