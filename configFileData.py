import readConfigFile

class configFileData:
    def __init__(self):
        self.data = readConfigFile.getConfigFile()
        
    def getConfigData (self):
        return self.data

    def getSplashscreen (self):
        return self.data["Splashscreen"]

    def getTitleBar (self):
        return self.data["TitleBar"]

    def getTitle (self):
        return self.data["Title"]

    def getWelcomeScreen (self):
        return self.data["WelcomeScreen"]
