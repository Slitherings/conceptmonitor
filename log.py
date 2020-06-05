def log(tag, text):
    #info 
    if(tag == 'i'):
        print("[INFO] " + text)
    #Warning
    elif(tag == 'w'):
        print("[WARN] " + text)
    #Error
    elif(tag == 'e'):
        print("[ERROR] " + text)
    #Success
    elif(tag == 's'):
        print("[SUCCESS] " + text)