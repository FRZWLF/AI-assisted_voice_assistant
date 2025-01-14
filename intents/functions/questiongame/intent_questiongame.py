from loguru import logger
from chatbot import register_call
import os
import constants
import global_variables
import yaml
from marianMTModels import Translator

YES = ["JA", "J", "YES", "Y", "OUI", "O", "SÍ", "SI", "S", "はい", "ええ", "ДА", "Д"]
NO = ["NEIN", "N", "NO", "NON", "いいえ", "いや", "НЕТ", "Н"]
PROBABLY = ["VIELLEICHT", "PROBABLY", "PEUT-ÊTRE", "POSSIBLE", "QUIZÁS", "TAL VEZ", "PROBABLEMENTE", "FORSE", "PROBABILMENTE", "多分", "恐らく", "ВОЗМОЖНО", "МОЖЕТ БЫТЬ"]
PROBABLY_NOT = ["WAHRSCHEINLICH NICHT", "EHER NICHT", "PROBABLY NOT", "PROBABLEMENT PAS", "PEUT-ÊTRE PAS", "PROBABLEMENTE NO", "QUIZÁS NO", "TAL VEZ NO", "PROBABILMENTE NO", "FORSE NO", "多分違う", "恐らく違う", "СКОРЕЕ НЕТ", "МАЛОВЕРОЯТНО"]

question_game_session = None


@register_call("startQuestionGame")
def startQuestionGame(session_id = "general", dummy=0):
    logger.info("Starte neues Fragespiel.")
    global question_game_session
    question_game_session = Q20Session()
    global_variables.context = questionGameAnswer
    return question_game_session.askQuestion()

def questionGameAnswer(answer=""):
    answer = answer.strip()
    logger.debug("Antwort '" + str(answer) + "' erhalten.")
    global question_game_session
    if not question_game_session is None:
        answer_value = question_game_session.evaluateAnswer(answer)
        for i in range(len(question_game_session.items)):
            question_game_session.items[i].updateCertainty(answer_value, question_game_session.current_question, len(question_game_session.questions))
        question = question_game_session.askQuestion()
        if question:
            logger.info("Die nächste Frage ist {}.", question)
            return question
        else:
            logger.info("Das war die letzte Frage.")
            final_answer = question_game_session.getAnswer()
            logger.info("Ermittelte Antwort für Fragespiel ist: {} ", str(final_answer))
            question_game_session.clearSession()
            global_variables.context = None
            question_game_session = None
            return final_answer
    else:
        return question_game_session.PLEASE_START_NEW_GAME

# Danke an https://github.com/FergusGriggs/20q
class Q20Session():

    def __init__(self):
        self.questions = []
        self.items = []
        self.current_question = 0

        # Lese die Konfiguration
        config_path = constants.find_data_file(os.path.join('intents','functions','questiongame','config_questiongame.yml'))
        cfg = None
        with open(config_path, "r", encoding='utf8') as ymlfile:
            cfg = yaml.load(ymlfile, Loader=yaml.FullLoader)

        # Holen der Sprache aus der globalen Konfigurationsdatei
        LANGUAGE = global_variables.voice_assistant.cfg['assistant']['language']
        self.translator = Translator(source_lang="en", dest_lang=LANGUAGE)

        self.PLEASE_START_NEW_GAME = cfg['intent']['questiongame'][LANGUAGE]['please_start_new_game']
        self.GUESS = cfg['intent']['questiongame'][LANGUAGE]['i_guess']

        items_path = constants.find_data_file(os.path.join('intents','functions','questiongame', 'items.txt'))
        questions_path = constants.find_data_file(os.path.join('intents','functions','questiongame', 'questions.txt'))

        itemData=open(items_path, encoding="utf-8")
        data=itemData.readlines()
        for i in range(len(data)):
            subdata=data[i].rstrip("\n").split(":")
            questionFloats=subdata[2][1:-1].split(",")
            for i in range(len(questionFloats)):
                questionFloats[i]=round(float(questionFloats[i]),4)
            self.items.append(Item(subdata[0],int(subdata[1]),questionFloats, len(self.items)))
        questionData=open(questions_path, encoding="utf-8")
        data=questionData.readlines()
        for i in range(len(data)):
            self.questions.append(Question(data[i].rstrip("\n"), len(self.questions)))
        questionData.close()

    def askQuestion(self):
        if self.current_question < len(self.questions):
            question = self.questions[self.current_question].string
            translated_question = self.translator.translate([question])[0]  # Übersetze die Frage
            self.current_question += 1
            return translated_question
        else:
            return None

    def getAnswer(self):
        selectedData = self.evaluateCertainties()
        item_name = self.items[selectedData[0]].name
        translated_item = self.translator.translate([item_name])[0]  # Übersetze den Namen des Items
        result = self.GUESS.format(str(round(100*selectedData[1],2)), translated_item.capitalize())
        return result

    def evaluateAnswer(self, answer):
        if answer.upper() in YES:
            a = 1
        elif answer.upper() in NO:
            a = -1
        elif answer.upper() in PROBABLY:
            a = 0.2
        elif answer.upper() in PROBABLY_NOT:
            a = -0.2
        else:
            a = 0
        return a

    def evaluateCertainties(self):
        maxi=0
        selected=-1
        for i in range(len(self.items)):
            if self.items[i].certainty>maxi:
                maxi=self.items[i].certainty
                selected=i
        return [selected, maxi]

    def clearSession(self):
        for i in range(len(self.items)):
            self.items[i].certainty=0

class Question():
    def __init__(self, string, id):
        self.string=string
        self.index=id

class Item():
    def __init__(self, name, guessNum, questionFloats, id):
        self.name=name
        self.guessNum=guessNum
        self.questionFloats=questionFloats
        self.index=id
        self.certainty=0

    def updateCertainty(self, val, current_question, num_questions):
        self.certainty+=(1-abs(val-self.questionFloats[current_question-1]))/num_questions