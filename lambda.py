import os, boto3, random, api_score, process_score, requests, datetime, locale, json
from dateutil.relativedelta import relativedelta
from boto3.dynamodb.conditions import Attr
from api_score import *

escalation_intent_name = os.getenv('ESCALATION_INTENT_NAME', None)

client = boto3.client('comprehend')

locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')

DYNAMODB = boto3.resource('dynamodb')
DYNAMO_TABLE_NAME = "TestIBK"
DYNAMO_TABLE = DYNAMODB.Table(DYNAMO_TABLE_NAME)

response_card_buttons = [
            {"text": "Si", "value": "Si"},
            {"text": "No", "value": "No"}
        ]

dnidict = {
          "42721353": "60544300",
          "71428797": "60544299",
          "44204397": "60544298",
          "44654479": "60544296",
          "48131154": "60544297"
        }

def lambda_handler(event, context):
    
    texthelp = "¿Puedo ayudarte en algo mas?"
    texthelpr = fun_select('Dime, puedo ayudarte en algo mas?','Si, dime en que mas te puedo asistir','Claro, dime que otra pregunta tienes.')
    textbye = 'Ok, que tengas un buen dia'
    dynamo_response = DYNAMO_TABLE.scan(FilterExpression=Attr("parameter_id").eq("contador"))
    current_retry = int(dynamo_response['Items'][0]['current_retry'])
    headers = {
    'Ocp-Apim-Subscription-Key': '24cd4cdf92874b2c9ce954ceedd105cf',
    'Authorization': 'Basic Y2ltYXVhdDpZMmx0WVhWaGRBPT0=',
    'Content-Type': 'application/x-www-form-urlencoded',
    'Cookie': 'visid_incap_2119127=JvFjVjBAQ2m8BrvQ3VFZVLidm2MAAAAAQUIPAAAAAAAfdKbJ/jlewfFtpHGGjrbV; incap_ses_129_2519394=kDancnQRVTVVKcr85UzKASKMLWQAAAAAj3KMBWyL2VZdSDWO4EtUtQ==; nlbi_2519394=M0ZyVWvp2AVEG5Gxu7FuQAAAAABsCpncGjSZjIHOiOkqgL0D; visid_incap_2519394=uFJnexjOTH2PU+Fney/fUpDlXmIAAAAAQUIPAAAAAADms1KsV84CzGHs5BbB4bpF'
    }
    
    data = {
      'grant_type': 'client_credentials',
      'scope': 'all'
    }
    
    response = requests.post('https://apis.uat.interbank.pe/hub-security/v2/oauth/token', headers=headers, data=data)
    
    token = response.json()['access_token']
    print("Token: ", token)
    
    if current_retry >= 6:
        ESCALATION_INTENT_MESSAGE="Parece que está teniendo problemas con nuestro servicio. ¿Te gustaría ser transferido a un asociado?"
        current_retry = 0
        field = 'current_retry'
        updateDynamoDB(DYNAMO_TABLE,field,current_retry)
        result = create_result('Close','saludo', ESCALATION_INTENT_MESSAGE)
        return result
    
    elif event['sessionState']['intent']['name']=='saludo':
    	print("logica saludo")
    	nombre = event['sessionState']['intent']['slots']['nombre']['value']['originalValue']
    	dni = event['sessionState']['intent']['slots']['dni']['value']['originalValue']
    	print(nombre)
    	print(dni)
    	codunico = dnidict[dni]
    	print(codunico)
    	result = create_saludo_result(nombre,dni,codunico)
    	return result
    	
    elif event['interpretations'][0]['intent']['name']=='puntajebajo':
        sentiment=client.detect_sentiment(Text=event['inputTranscript'],LanguageCode='es')['Sentiment']
        current_retry = int(dynamo_response['Items'][0]['current_retry'])
        current_retry = escalation_sentiment(sentiment,current_retry)
        field = 'current_retry'
        reintento = str(current_retry)
        updateDynamoDB(DYNAMO_TABLE,field,current_retry)
        input_transcript = event['inputTranscript'].lower()
        print("logica puntajebajo")
        session_attributes = event['sessionState'].get('sessionAttributes', {})
        dni = session_attributes.get('dni', '')
        codunico = session_attributes.get('codunico', '')
        contador = session_attributes.get('contador', '')
        print("dni:", dni)
        print("codunico:", codunico)
        print("Llamado a la API_HOME_SCORE")
        headers = {
            'Ocp-Apim-Subscription-Key': '75e37de83a544a709466ca0f82e1a935',
            'Authorization': f'Bearer {token}'
        }
        
        url = f'https://apis.uat.interbank.pe/scoring/v2/score/ecosystem/customers/00{codunico}/home-score'
        print(url)
        response = requests.get(url, headers=headers)
        
        json_apihomescore = response.json()
        
        print(json_apihomescore)
        
        v=0
        nv=0
        for i in json_apihomescore['activeVars']:
            if i["level"].lower()=="por mejorar":
                respuesta = fun_tab_rec(i["description"])
                text1 = "Por ejemplo, veo que este mes tienes oportunidad de mejorar en "+ i["description"] +". En algunos casos, el puntaje puede ir bajando cuando el factor de evaluación se mantiene en un estado que no es el ideal por mucho tiempo. Te recomiendo"+ respuesta 
            
                v=1
                break
            
        if 'commingSoonVars' in json_apihomescore and json_apihomescore['commingSoonVars']:    
            for i in json_apihomescore['commingSoonVars']:
                    
                if i["level"].lower()=="por mejorar":
                    
                    text2 = " En tu caso vemos que se debe a "+ i["description"] +" que aún no se encuentra visible en el app . En este caso te recomiendo "+ i["description"] +" Estamos trabajando para que podamos disponibilizar más información que les sea de ayuda para mejorar su salud financiera."
                    
                    nv=1
                else:
                    text3 = "Sin embargo, en este caso tu puntaje ha variado debido a uno de los factores que utiliza el modelo de riesgos que tenemos en el banco y que cuenta con la información encriptada sobre nuestros clientes para no poner en riesgo su privacidad."
                    text4 = "De todas formas, te comento que el puntaje es el conjunto de factores que provienen tanto de tu comportamiento crediticio en el sistema financiero como tu actividad financiera dentro de Interbank. Pero también, consideramos información proveniente de centrales de riesgo, donde se consideran tus compromisos de pago con otras entidades no financieras como el pago de tus servicios, teléfono, entre otros."
                    text5 = "Te recomiendo validar si en algún momento no pudiste pagar a tiempo alguno de estos servicios no financieros ya que eso podría estar impactando tu evaluación si es que se dio con frecuencia, así como autoevaluar si tu buen comportamiento financiero se ha mantenido en el tiempo, sin excepciones."
                    
            
        else:
            text3 = "Sin embargo, en este caso tu puntaje ha variado debido a uno de los factores que utiliza el modelo de riesgos que tenemos en el banco y que cuenta con la información encriptada sobre nuestros clientes para no poner en riesgo su privacidad."
            text4 = "De todas formas, te comento que el puntaje es el conjunto de factores que provienen tanto de tu comportamiento crediticio en el sistema financiero como tu actividad financiera dentro de Interbank. Pero también, consideramos información proveniente de centrales de riesgo, donde se consideran tus compromisos de pago con otras entidades no financieras como el pago de tus servicios, teléfono, entre otros."
            text5 = "Te recomiendo validar si en algún momento no pudiste pagar a tiempo alguno de estos servicios no financieros ya que eso podría estar impactando tu evaluación si es que se dio con frecuencia, así como autoevaluar si tu buen comportamiento financiero se ha mantenido en el tiempo, sin excepciones."
                
        if input_transcript == 'no':
            result = create_result('Close','puntajebajo',textbye)
            return result
            
        elif input_transcript == 'si':
            result = create_result('Close','puntajebajo',texthelpr)
            return result
        
        else:
            if (v==0) & (nv==0):
                result = create_response_card_result('ConfirmIntent','puntajebajo','Elige una de las siguientes:',text3,text4,text5,texthelp, response_card_buttons = response_card_buttons)
                return result
                
            elif v==1:
                result = create_response_card_result('ConfirmIntent','puntajebajo','Elige una de las siguientes:',text1,texthelp, response_card_buttons = response_card_buttons)
                return result
                
            elif nv==1:
                result = create_response_card_result('ConfirmIntent','puntajebajo','Elige una de las siguientes:',text2,texthelp, response_card_buttons = response_card_buttons)
                return result
                
            else:
                pass
        
                
    elif event['interpretations'][0]['intent']['name']=='punajebajosentimiento':
        sentiment=client.detect_sentiment(Text=event['inputTranscript'],LanguageCode='es')['Sentiment']
        ESCALATION_INTENT_MESSAGE="Parece que está teniendo problemas con nuestro servicio. ¿Te gustaría ser transferido a un asociado?"
        current_retry = int(dynamo_response['Items'][0]['current_retry'])
        current_retry = escalation_sentiment(sentiment,current_retry)
        field = 'current_retry'
        reintento = str(current_retry)
        updateDynamoDB(DYNAMO_TABLE,field,current_retry)
        input_transcript = event['inputTranscript'].lower()
        print("logica puntajebajosentimiento")
        session_attributes = event['sessionState'].get('sessionAttributes', {})
        dni = session_attributes.get('dni', '')
        codunico = session_attributes.get('codunico', '')
        print("dni:", dni)
        print("codunico:", codunico)
        print("Llamado a la API_HOME_SCORE")
        
        headers = {
            'Ocp-Apim-Subscription-Key': '75e37de83a544a709466ca0f82e1a935',
            'Authorization': f'Bearer {token}'
        }
        
        url = f'https://apis.uat.interbank.pe/scoring/v2/score/ecosystem/customers/00{codunico}/home-score'
        print(url)
        response = requests.get(url, headers=headers)
        
        json_apihomescore = response.json()
        
        print(json_apihomescore)
        
        name=session_attributes.get('nombre', '')
        print(name)
        textn = "Entiendo la confusión "+name+". Muchas personas piensan que el puntaje crediticio solo es un reflejo de tu comportamiento de pagos; sin embargo, la evaluación incluye mucho más. Si bien es uno de los más importantes debes tener en cuenta que existen otros factores tanto internos (propios de Interbank) como externos (sistema financiero) que componen tu evaluación. Por ejemplo, el uso responsable de tu linea de crédito, tu capacidad de ahorro, entre otros."
        text = name + ", muchas personas piensan que el puntaje crediticio solo es un reflejo de tu comportamiento de pagos; sin embargo, la evaluación incluye mucho más. Si bien es uno de los más importantes debes tener en cuenta que existen otros factores tanto internos (propios de Interbank) como externos (sistema financiero) que componen tu evaluación. Por ejemplo, el uso responsable de tu linea de crédito, tu capacidad de ahorro, entre otros. "
        v=0
        nv=0
        for i in json_apihomescore['activeVars']:
            if (i["level"].lower()=="por mejorar") & (i["description"].lower()=="pago a tiempo"):
                
                text1 = "En este caso, verifico que este mes tu factor 'Pago a tiempo' se encuentra 'Por mejorar' y esto puede deberse a que tuviste un retraso en el pago de tus tarjetas en meses anteriores. Te recuerdo que la información que se muestra en el detalle de este factor se reporta con un desfase de 2 meses. Si quieres revisar el detalle de los meses que vienes pagando a tiempo puedes encontrarlo haciendo click en el factor Pago a tiempo."
                
                v=1
                break
            else:
                respuesta = fun_tab_rec(i["description"])
                text2 = "Tu puntaje puede bajar por diversos motivos. Los principales los puedes encontrar en ‘Mis Finanzas’. Por ejemplo, veo que este mes tienes oportunidad de mejorar en "+ i["description"] +". En algunos casos, el puntaje puede ir bajando cuando el factor de evaluación se mantiene en un estado que no es el ideal por mucho tiempo. Te recomiendo"+ respuesta
        
        if 'commingSoonVars' in json_apihomescore and json_apihomescore['commingSoonVars']:
            for i in json_apihomescore['commingSoonVars']:
                    
                if (i["level"].lower()=="por mejorar") & (i["description"].lower()=="pago a tiempo"):
                    
                    text1 = "En este caso, verifico que este mes tu factor 'Pago a tiempo' se encuentra 'Por mejorar' y esto puede deberse a que tuviste un retraso en el pago de tus tarjetas en meses anteriores. Te recuerdo que la información que se muestra en el detalle de este factor se reporta con un desfase de 2 meses. Si quieres revisar el detalle de los meses que vienes pagando a tiempo puedes encontrarlo haciendo click en el factor Pago a tiempo."
                    
                    nv=1
                    break
                else:
                    pass
        else:
            pass
        
        text3 = "Sin embargo, en este caso tu puntaje ha variado debido a uno de los factores que utiliza el modelo de riesgos que tenemos en el banco y que cuenta con la información encriptada sobre nuestros clientes para no poner en riesgo su privacidad."
        text4 = "De todas formas, te comento que el puntaje es el conjunto de factores que provienen tanto de tu comportamiento crediticio en el sistema financiero como tu actividad financiera dentro de Interbank. Pero también, consideramos información proveniente de centrales de riesgo, donde se consideran tus compromisos de pago con otras entidades no financieras como el pago de tus servicios, teléfono, entre otros."
        text5 = "Te recomiendo validar si en algún momento no pudiste pagar a tiempo alguno de estos servicios no financieros ya que eso podría estar impactando tu evaluación si es que se dio con frecuencia, así como autoevaluar si tu buen comportamiento financiero se ha mantenido en el tiempo, sin excepciones."
                
        

        if input_transcript == 'no':
            result = create_result('Close','punajebajosentimiento',textbye)
            return result
            
        elif input_transcript == 'si':
            result = create_result('Close','punajebajosentimiento',texthelpr)
            return result
        
        else:
            if sentiment == 'NEGATIVE':
                if  (v==0) & (nv==0):
                    result = create_response_card_result('ConfirmIntent','punajebajosentimiento','Elige una de las siguientes:',textn,text3,text4,text5,texthelp, response_card_buttons = response_card_buttons)
                    return result
                elif v == 1 | nv == 1:
                    result = create_response_card_result('ConfirmIntent','punajebajosentimiento','Elige una de las siguientes:',textn,text1,texthelp, response_card_buttons = response_card_buttons)
                    return result
                else:
                    result = create_response_card_result('ConfirmIntent','punajebajosentimiento','Elige una de las siguientes:',textn,text2,texthelp, response_card_buttons = response_card_buttons)
                    return result
                    
                
            else:
                if (v==0) & (nv==0):
                    result = create_response_card_result('ConfirmIntent','punajebajosentimiento','Elige una de las siguientes:',text,text3,text4,text5,texthelp, response_card_buttons = response_card_buttons)
                    return result
                    
                elif v == 1 | nv == 1:
                    result = create_response_card_result('ConfirmIntent','punajebajosentimiento','Elige una de las siguientes:',text,text1,texthelp, response_card_buttons = response_card_buttons)
                    return result
                   
                else:
                    result = create_response_card_result('ConfirmIntent','punajebajosentimiento','Elige una de las siguientes:',text,text2,texthelp, response_card_buttons = response_card_buttons)
                    return result
        
    elif event['interpretations'][0]['intent']['name']=='mejorarpuntaje':
        sentiment=client.detect_sentiment(Text=event['inputTranscript'],LanguageCode='es')['Sentiment']
        current_retry = int(dynamo_response['Items'][0]['current_retry'])
        current_retry = escalation_sentiment(sentiment,current_retry)
        field = 'current_retry'
        reintento = str(current_retry)
        updateDynamoDB(DYNAMO_TABLE,field,current_retry)
        input_transcript = event['inputTranscript'].lower()
        print("logica mejorar puntaje")
        session_attributes = event['sessionState'].get('sessionAttributes', {})
        dni = session_attributes.get('dni', '')
        codunico = session_attributes.get('codunico', '')
        print("dni:", dni)
        print("codunico:", codunico)
        print("Llamado a la API_HOME_SCORE")
        
        headers = {
            'Ocp-Apim-Subscription-Key': '75e37de83a544a709466ca0f82e1a935',
            'Authorization': f'Bearer {token}'
        }
        
        url = f'https://apis.uat.interbank.pe/scoring/v2/score/ecosystem/customers/00{codunico}/home-score'
        print(url)
        response = requests.get(url, headers=headers)
        
        json_apihomescore = response.json()
        
        print(json_apihomescore)
        
        v=0
        nv=0
        for i in json_apihomescore['activeVars']:
            if i["level"].lower()=="por mejorar":
                respuesta = fun_tab_rec(i["description"])
                text1 = "Un buen Puntaje Crediticio es el reflejo de una buena Salud Financiera, por eso en Interbank te ayudamos a mantener el control de algunos de los principales factores que evaluamos en tu Puntaje. Puedes encontrar el detalle de cada uno en ‘Mis Finanzas’. Por ejemplo, veo que este mes tienes oportunidad de mejorar en "+ i["description"] +". En algunos casos, el puntaje puede ir bajando cuando el factor de evaluación se mantiene en un estado que no es el ideal por mucho tiempo."
                text1n =  "Te recomiendo"+ respuesta
                v=1
                break
        
        if 'commingSoonVars' in json_apihomescore and json_apihomescore['commingSoonVars']:    
            for i in json_apihomescore['commingSoonVars']:
                    
                if i["level"].lower()=="por mejorar":
                    
                    text2 = "Un buen Puntaje Crediticio es el reflejo de una buena Salud Financiera, por eso en Interbank te ayudamos a mantener el control de algunos de los principales factores que evaluamos en tu Puntaje. Puedes encontrar el detalle de cada uno en ‘Mis Finanzas’. Por ejemplo, veo que este mes tienes oportunidad de mejorar en "+ i["description"] +". En algunos casos, el puntaje puede ir bajando cuando el factor de evaluación se mantiene en un estado que no es el ideal por mucho tiempo. Te recomiendo "+ i["description"] +"."
                    
                    nv=1
                    break
                else:
                    
                    text3 = "Un buen Puntaje Crediticio es el reflejo de una buena Salud Financiera. Cada mes te evaluamos en base a un conjunto de factores que provienen tanto de tu comportamiento crediticio en el sistema financiero como tu actividad financiera dentro de Interbank. Asimismo, consideramos información proveniente de centrales de riesgo, donde se considera tus compromisos de pago con otras entidades no financieras como el pago de tus servicios, teléfono, entre otros."
                    text4 = " Por eso, para mantener o mejorar tu Puntaje Crediticio es importante que mantengas un buen comportamiento no solo con el banco si no con cualquier entidad con la que mantengas compromisos de pago. Además, hagas uso responsable de tus productos financieros y mantengas buenos hábitos de ahorro e inversión a largo plazo."
        
        else:
            pass
        
        if input_transcript == 'no' in input_transcript:
            result = create_result('Close','mejorarpuntaje',textbye)
            return result
            
        elif input_transcript == 'si' in input_transcript:
            result = create_result('Close','mejorarpuntaje',texthelpr)
            return result
        
        else:
            if (v==0) & (nv==0):
                result = create_response_card_result('ConfirmIntent','mejorarpuntaje','Elige una de las siguientes:',text3,text4,texthelp, response_card_buttons = response_card_buttons)
                return result
               
            elif v==1:
                result = create_response_card_result('ConfirmIntent','mejorarpuntaje','Elige una de las siguientes:',text1,text1n,texthelp, response_card_buttons = response_card_buttons)
                return result
                
            elif nv==1:
                result = create_response_card_result('ConfirmIntent','mejorarpuntaje','Elige una de las siguientes:',text2,texthelp, response_card_buttons = response_card_buttons)
                return result
            
            else:
                    pass
            #return result
    
    elif event['interpretations'][0]['intent']['name']=='productofinanciero':
        sentiment=client.detect_sentiment(Text=event['inputTranscript'],LanguageCode='es')['Sentiment']
        ESCALATION_INTENT_MESSAGE="Parece que está teniendo problemas con nuestro servicio. ¿Te gustaría ser transferido a un asociado?"
        current_retry = int(dynamo_response['Items'][0]['current_retry'])
        current_retry = escalation_sentiment(sentiment,current_retry)
        field = 'current_retry'
        reintento = str(current_retry)
        updateDynamoDB(DYNAMO_TABLE,field,current_retry)
        input_transcript = event['inputTranscript'].lower()
        print("logica producto financiero")
        print("llama api")
        ##llamar a la API_ONBOARDING:
        session_attributes = event['sessionState'].get('sessionAttributes', {})
        dni = session_attributes.get('dni', '')
        codunico = session_attributes.get('codunico', '')
        print("dni:", dni)
        print("codunico:", codunico)
        print("Llamado a la API_ONBOARDING")
        
        headers = {
            'Ocp-Apim-Subscription-Key': '75e37de83a544a709466ca0f82e1a935',
            'Authorization': f'Bearer {token}'
        }
        
        url = f'https://apis.uat.interbank.pe/scoring/v2/score/ecosystem/customers/00{codunico}/onboarding'
        print(url)
        response = requests.get(url, headers=headers)
        
        json_apihomescore = response.json()
        
        print(json_apihomescore)
        
        if 'sessionState' in event and event['sessionState'] is not None \
                and 'intent' in event['sessionState'] and event['sessionState']['intent'] is not None \
                and 'slots' in event['sessionState']['intent'] and event['sessionState']['intent']['slots'] is not None \
                and 'producto' in event['sessionState']['intent']['slots'] and event['sessionState']['intent']['slots']['producto'] is not None \
                and 'value' in event['sessionState']['intent']['slots']['producto'] and event['sessionState']['intent']['slots']['producto']['value'] is not None \
                and 'originalValue' in event['sessionState']['intent']['slots']['producto']['value']:
            producto = event['sessionState']['intent']['slots']['producto']['value']['originalValue']
        else:
            producto = ''
        if (json_apihomescore['score']['level'].lower() == "muy bajo") | (json_apihomescore['score']['level'].lower() == "bajo") | (json_apihomescore['score']['level'].lower() == "regular"):
            text="Por ejemplo, tu Puntaje Crediticio es un indicador que nos ayuda a conocer cómo se encuentra tu salud financiera, por lo que mantener un buen Puntaje Crediticio de manera constante es una buena forma de acercarte a un producto financiero."
            text2="Puedo ver que tu Puntaje Crediticio por el momento se encuentra en nivel "+ json_apihomescore['score']['level'].lower() + ". Aún tienes oportunidad de seguir mejorándolo para acercarte al producto que buscas. Descubre en el detalle de tu evaluación los factores que puedes mejorar para que tu Puntaje Crediticio suba de nivel."
        elif (json_apihomescore['score']['level'].lower() == "bueno") | (json_apihomescore['score']['level'].lower() == "excelente"):
            text="Para ello nos ayuda poder conocerte lo mejor posible, por ejemplo una de las maneras de evaluarte mejor es a través de las cuentas de ahorro que mantengas con nosotros ya que nos permiten evaluar tus ingresos y tu capacidad de ahorro en el tiempo."
            text2="Así, tener tu cuenta sueldo con nosotros es una buena forma de empezar a generar un historial o también puedes acercarte a nuestras tiendas y presentar boletas para sustentar tus ingresos. Así te iremos conociendo más y estarás cada vez mas cerca a acceder a un "+ producto +"."
        else:
            pass
        
        if input_transcript == 'no':
            result = create_result('Close','productofinanciero',textbye)
            return result
            
        elif input_transcript == 'si':
            result = create_result('Close','productofinanciero',texthelpr)
            return result
        
        else:
            result = create_response_card_result('ConfirmIntent','productofinanciero','Elige una de las siguientes:',text,text2,texthelp, response_card_buttons = response_card_buttons)
            return result
        #return result
        
    elif event['interpretations'][0]['intent']['name']=='invertir':
        sentiment=client.detect_sentiment(Text=event['inputTranscript'],LanguageCode='es')['Sentiment']
        current_retry = int(dynamo_response['Items'][0]['current_retry'])
        current_retry = escalation_sentiment(sentiment,current_retry)
        field = 'current_retry'
        reintento = str(current_retry)
        updateDynamoDB(DYNAMO_TABLE,field,current_retry)
        input_transcript = event['inputTranscript'].lower()
        ESCALATION_INTENT_MESSAGE="Parece que está teniendo problemas con nuestro servicio. ¿Te gustaría ser transferido a un asociado?"
        print("logica invertir")
        print("llama api")
        ##llamar a la API_HOME_SCORE:
        session_attributes = event['sessionState'].get('sessionAttributes', {})
        dni = session_attributes.get('dni', '')
        codunico = session_attributes.get('codunico', '')
        print("dni:", dni)
        print("codunico:", codunico)
        print("Llamado a la API_ONBOARDING")
        
        headers = {
            'Ocp-Apim-Subscription-Key': '75e37de83a544a709466ca0f82e1a935',
            'Authorization': f'Bearer {token}'
        }
        
        url = f'https://apis.uat.interbank.pe/scoring/v2/score/ecosystem/customers/00{codunico}/home-score'
        print(url)
        response = requests.get(url, headers=headers)
        
        json_apihomescore = response.json()
        
        print(json_apihomescore)
        
        name=event["sessionState"]["sessionAttributes"]["nombre"]
        print(name)
        
        textn = "Lamento tu malestar "+name+" ."
        text = "Voy a explicarte mejor la importancia de este factor inversión en tu Puntaje. Dentro de los comportamientos que reflejan una buena salud financiera, y por tanto, una buena capacidad de pago de créditos, se encuentran tanto el ahorro a corto como a largo plazo (inversión). En particular, el ahorro a largo plazo refleja que no necesitas con urgencia el efectivo que has depositado en cuentas como CTS, plazo fijo y fondos mutuos. Por ley de protección al consumidor de la SBS, los bancos no comparten este tipo de información en el sistema financiero y solo podríamos contar con ella en caso tengas tus ahorros con nosotros, por eso es importante contar con esa información para evaluarte mejor."
        
        v=0
        nv=0
        for i in json_apihomescore['activeVars']:
            if (i["id"].lower()=="investments") & (i["level"].lower()=="por mejorar"):
                
                text2 = "Veo que te encuentras en el nivel Por Mejorar de este factor, lo cual significa que no contamos con información de tus cuentas de inversión en Interbank. Te recomiendo que evalúes las opciones de inversión que tenemos para ti para ver si alguna es de tu interés, y asi podamos incluir esta información en tu evaluación como un punto a favor.. Puedes verlas aquí XXX"
            
            elif (i["id"].lower()=="investments") & (i["level"].lower()=="mejor"):
                
                text2 = "Veo que te encuentras en el nivel Mejor de este factor, lo cual indica que ya tienes una cuenta de inversión con nosotros, pero no cuenta con el saldo suficiente. Si deseas, puedes depositar %valor_inversión_pendiente% en tu cuenta y mantenerla por 3 meses para subir de nivel. En caso tu cuenta sea de CTS, estoy seguro de que pronto llegarás al monto necesario."
                
                
            elif (i["id"].lower()=="investments") & (i["level"].lower()=="bien"):
                text2 = "Veo que te encuentras Bien en este factor lo cual te ayudará a mantener un Buen Puntaje Crediticio. ¡Sigue así!"
                
            else:
                pass
        
        if input_transcript == 'no':
            result = create_result('Close','invertir',textbye)
            return result
            
        elif input_transcript == 'si':
            result = create_result('Close','invertir',texthelpr)
            return result
        
        else:
            if sentiment == 'NEGATIVE':
                result = create_response_card_result('ConfirmIntent','invertir','Elige una de las siguientes:',textn,text,text2,texthelp, response_card_buttons = response_card_buttons)
                return result
                
            else:
                result = create_response_card_result('ConfirmIntent','invertir','Elige una de las siguientes:',text,text2,texthelp, response_card_buttons = response_card_buttons)
                return result
        #return result
        
    elif event['interpretations'][0]['intent']['name']=='deudapuntaje':
        sentiment=client.detect_sentiment(Text=event['inputTranscript'],LanguageCode='es')['Sentiment']
        current_retry = int(dynamo_response['Items'][0]['current_retry'])
        current_retry = escalation_sentiment(sentiment,current_retry)
        field = 'current_retry'
        reintento = str(current_retry)
        updateDynamoDB(DYNAMO_TABLE,field,current_retry)
        print("logica deuda pagada puntaje")
        print("llama api")
        ##llamar a la API_HOME_SCORE:
        session_attributes = event['sessionState'].get('sessionAttributes', {})
        dni = session_attributes.get('dni', '')
        codunico = session_attributes.get('codunico', '')
        print("dni:", dni)
        print("codunico:", codunico)
        print("Llamado a la API_ONBOARDING")
        
        headers = {
            'Ocp-Apim-Subscription-Key': '75e37de83a544a709466ca0f82e1a935',
            'Authorization': f'Bearer {token}'
        }
        
        url = f'https://apis.uat.interbank.pe/scoring/v2/score/ecosystem/customers/00{codunico}/onboarding'
        print(url)
        response = requests.get(url, headers=headers)
        
        json_apihomescore = response.json()
        
        print(json_apihomescore)
        
        name=session_attributes.get('nombre', '')
        print(name)
        text = "Tu Puntaje se construye con información del Reporte Consolidado de Créditos (RCC) de la Superintendencia de Banca, Seguros y AFP (SBS) que tarda aproximadamente 1 mes en consolidar la información de las deudas de los peruanos en todos los bancos."
        text1 = "Esto genera que la información sobre deudas que mostramos en el app cuente con un desfase de 2 meses. Es por esto que es posible que aún veas una deuda pasada en tu herramienta de puntaje crediticio. "
        
        #LLAMADO A API
        month = json_apihomescore["score"]["month"]
        year = json_apihomescore["score"]["year"]
        
        score_month = datetime.datetime.strptime(f"{month} {year}", "%B %Y")
        
        two_months_ago = score_month - relativedelta(months=2)
        one_month_after = two_months_ago + relativedelta(months=1)
        three_months_after = two_months_ago + relativedelta(months=3)
       
        input_transcript = event['inputTranscript'].lower() # Convertir a minúsculas
        print(input_transcript)
        
        if input_transcript == 'no':
            result = create_result('Close','deudapuntaje',textbye)
            return result
            
        elif input_transcript == 'si':
            result = create_result('Close','deudapuntaje',texthelpr)
            return result
        
        elif 'no entendi' in input_transcript or 'no me quedo claro' in input_transcript or 'me podrias dar un ejemplo' in input_transcript:
            text2 = f"Claro por ejemplo, asumamos que tu deuda del mes de {two_months_ago.strftime('%B')} la pagaste en {one_month_after.strftime('%B')}. Al cierre del mes en que pagaste inicia el viaje de la información de la SBS con los bancos y para inicios de {three_months_after.strftime('%B')}  ya estará actualizado en tu Puntaje Crediticio"
            result = create_response_card_result('ConfirmIntent','deudapuntaje','Elige una de las siguientes:',text2,texthelp, response_card_buttons = response_card_buttons)
            return result
            
        else:
            result = create_result('ConfirmIntent','deudapuntaje',text,text1) 
            return result
            
    elif event['interpretations'][0]['intent']['name']=='evaluacionpuntaje':
        sentiment=client.detect_sentiment(Text=event['inputTranscript'],LanguageCode='es')['Sentiment']
        current_retry = int(dynamo_response['Items'][0]['current_retry'])
        current_retry = escalation_sentiment(sentiment,current_retry)
        field = 'current_retry'
        reintento = str(current_retry)
        updateDynamoDB(DYNAMO_TABLE,field,current_retry)
        input_transcript = event['inputTranscript'].lower()
        print("logica desacuerdo evaluacion")
        session_attributes = event['sessionState'].get('sessionAttributes', {})
        name=session_attributes.get('nombre', '')
        print(name)
        text = "Entiendo tu inconformidad " + name + ", sin embargo, es importante comentarte que el Puntaje Crediticio que visualizas en Interbank es solo de uso interno"
        text1 = "No se relaciona con otras calificaciones de riesgos externas como Equifax o la SBS ni se reporta como score a otras entidades financieras."
        text2 = 'Cuéntame para ayudarte, ¿cuál es el motivo de tu inconformidad?'
        response_card_buttons_intencion = [
           {"text": "¿Por qué bajó mi puntaje?","value": "¿Por qué bajó mi puntaje?"},
           {"text": "¿Por qué mi puntaje es bajo si yo pago a tiempo?","value": "¿Por qué mi puntaje es bajo si yo pago a tiempo?"},
           {"text": "¿Porque debo invertir para mejorar mi puntaje?","value": "¿Porque debo invertir para mejorar mi puntaje?"},
           {"text": "Ya pague mi deuda y sigue saliendo en mi puntaje","value": "Ya pague mi deuda y sigue saliendo en mi puntaje"},
           {"text": "¿Por qué no sale información en mi puntaje?","value": "¿Por qué no sale información en mi puntaje?"}
        ]
        
        result = create_response_card_result('Close','evaluacionpuntaje','Dudas Frecuentes',text,text1,text2, response_card_buttons = response_card_buttons_intencion)
        
        return result
        
    elif event['interpretations'][0]['intent']['name']=='actualizacionpuntaje':
        sentiment=client.detect_sentiment(Text=event['inputTranscript'],LanguageCode='es')['Sentiment']
        current_retry = int(dynamo_response['Items'][0]['current_retry'])
        current_retry = escalation_sentiment(sentiment,current_retry)
        field = 'current_retry'
        reintento = str(current_retry)
        updateDynamoDB(DYNAMO_TABLE,field,current_retry)
        print("logica actualizacion puntaje")
        print("llama api")
        ##llamar a la API_HOME_SCORE:
        session_attributes = event['sessionState'].get('sessionAttributes', {})
        dni = session_attributes.get('dni', '')
        codunico = session_attributes.get('codunico', '')
        print("dni:", dni)
        print("codunico:", codunico)
        print("Llamado a la API_ONBOARDING")
        
        headers = {
            'Ocp-Apim-Subscription-Key': '75e37de83a544a709466ca0f82e1a935',
            'Authorization': f'Bearer {token}'
        }
        
        url = f'https://apis.uat.interbank.pe/scoring/v2/score/ecosystem/customers/00{codunico}/onboarding'
        print(url)
        response = requests.get(url, headers=headers)
        
        json_apihomescore = response.json()
        
        session_attributes = event['sessionState'].get('sessionAttributes', {})
        
        name=session_attributes.get('nombre', '')
        print(name)
        
        month = json_apihomescore["score"]["month"]
        year = json_apihomescore["score"]["year"]
        
        score_month = datetime.datetime.strptime(f"{month} {year}", "%B %Y")

        two_months_ago = score_month - datetime.timedelta(days=60)
        
        score_date = datetime.datetime.strptime(f"{month} {year}", "%B %Y")
        next_month = score_date.replace(day=1) + datetime.timedelta(days=32)
        next_month = next_month.replace(day=1)
    
        # Calcular sexto día hábil
        business_days = 0
        current_day = next_month
        while business_days < 6:
            current_day += datetime.timedelta(days=1)
            weekday = current_day.weekday()
            if weekday < 5:
                business_days += 1
        
        dia_util = current_day.strftime('%d de %B')
        
        text = f"El Puntaje Crediticio se actualiza todos los meses en los primeros 6 – 8 días útiles del mes. Actualmente en tu app puedes ver tu puntaje de {score_month.strftime('%B')}, el cual cuenta con información del sistema financiero hasta {two_months_ago.strftime('%B')}."
        text1 = f"La actualización de {next_month.strftime('%B')} debería darse apróximadamente el {dia_util}. De todas formas, si has ingresado a ver tu puntaje este mes, te mandaremos una alerta cuando tu Puntaje se haya actualizado."
        
        #LLAMADO A API
        
        input_transcript = event['inputTranscript'].lower() # Convertir a minúsculas
        print(input_transcript)
        
        if input_transcript == 'no':
            result = create_result('Close','actualizacionpuntaje',textbye)
            return result
            
        elif input_transcript == 'si':
            result = create_result('Close','actualizacionpuntaje',texthelpr)
            return result
        
        else:
            result = create_response_card_result('ConfirmIntent','actualizacionpuntaje','Elige una de las siguientes:',text,text1,texthelp, response_card_buttons = response_card_buttons)
            return result
        
    elif event['interpretations'][0]['intent']['name']=='infopuntaje':
        sentiment=client.detect_sentiment(Text=event['inputTranscript'],LanguageCode='es')['Sentiment']
        current_retry = int(dynamo_response['Items'][0]['current_retry'])
        current_retry = escalation_sentiment(sentiment,current_retry)
        field = 'current_retry'
        reintento = str(current_retry)
        updateDynamoDB(DYNAMO_TABLE,field,current_retry)
        input_transcript = event['inputTranscript'].lower() # Convertir a minúsculas
        print("logica informacion puntaje")
        session_attributes = event['sessionState'].get('sessionAttributes', {})
        dni = session_attributes.get('dni', '')
        codunico = session_attributes.get('codunico', '')
        print("dni:", dni)
        print("codunico:", codunico)
        print("Llamado a la API_ONBOARDING")
        
        headers = {
            'Ocp-Apim-Subscription-Key': '75e37de83a544a709466ca0f82e1a935',
            'Authorization': f'Bearer {token}'
        }
        
        url = f'https://apis.uat.interbank.pe/scoring/v2/score/ecosystem/customers/00{codunico}/onboarding'
        print(url)
        response = requests.get(url, headers=headers)
        
        json_apihomescore = response.json()
        
        print(json_apihomescore)
        
        profile = json_apihomescore['score']['profile']
        level = json_apihomescore['score'].get('level')
        
        if input_transcript == 'no':
            result = create_result('Close','infopuntaje',textbye)
            return result
            
        elif input_transcript == 'si':
            result = create_result('Close','infopuntaje',texthelpr)
            return result
        
        else:
            if profile == 'MONOPRODUCTO TC' or profile == 'MULTIPRODUCTO':
                text = f"Verifico que si tienes un puntaje crediticio y te encuentras en el {level}."
                text1 = "En caso no veas información de algunos factores se debe a que el detalle de tu puntaje crediticio se esta procesando en la próxima actualización podrás ver todos los factores sin problemas."
                result = create_response_card_result('ConfirmIntent','infopuntaje','Elige una de las siguientes:',text,text1,texthelp, response_card_buttons = response_card_buttons)
                return result
            
            elif profile == 'PASIVERO':
                text2 = f"Verifico que si tienes un puntaje crediticio y te encuentras en el {level}."
                text3 = "En caso te refieras a que no sale información en algunos factores, esto se debe a que aún no cuentas con un crédito o préstamo que te permita ser evaluado por los factores de pago a tiempo y uso de línea de crédito."
                text4 = "Construye tu puntaje ahorrando en la alcancía y pronto tendrás la oportunidad de generar tu historial con una tarjeta con garantía."
                
                result = create_response_card_result('ConfirmIntent','infopuntaje','Elige una de las siguientes:',text2,text3,text4,texthelp, response_card_buttons = response_card_buttons)
                return result
                
                
            else:
                text5 = "Esto se debe a que el sistema de evaluación todavía no te reconoce como cliente activo al no tener información de tu actividad con el banco. "
                text6 = "Para tener una evaluación completa de Puntaje Crediticio deberás activar tu cuenta Interbank depositando desde S/10.Una vez activa te podremos dar el detalle completo de tu Puntaje Crediticio desde la siguiente actualización sin problema"
                
                result = create_response_card_result('ConfirmIntent','infopuntaje','Elige una de las siguientes:',text5,text6,texthelp, response_card_buttons = response_card_buttons)
                return result
                
                
    elif event['interpretations'][0]['intent']['name']=='FallbackIntent':
        sentiment=client.detect_sentiment(Text=event['inputTranscript'],LanguageCode='es')['Sentiment']
        current_retry = int(dynamo_response['Items'][0]['current_retry'])
        current_retry = escalation_sentiment(sentiment,current_retry)
        field = 'current_retry'
        reintento = str(current_retry)
        updateDynamoDB(DYNAMO_TABLE,field,current_retry)
        print("FallbackIntent")
        session_attributes = session_attributes = event['sessionState'].get('sessionAttributes', {})
        
        
        response = {
                "sessionState": {
                    "dialogAction": {
                        "type": "ElicitIntent",
                    },
                    "intent": {
                        "name": 'FallbackIntent',
                        "state": "Fulfilled"
                    }
                },
                'messages': [ 
                    {
                    'contentType': 'PlainText',
                    'content': 'Disculpa, no logro comprender tu consulta. Por favor, indicame si tu consulta se encuentra dentro de las siguientes opciones'
                    },
                    {
                      "contentType": "ImageResponseCard",
                      "imageResponseCard": {
                        "buttons": [
                          {
                            "text": "¿Por qué bajó mi puntaje?",
                            "value": "¿Por qué bajó mi puntaje?"
                          },
                          {
                            "text": "¿Por qué mi puntaje es bajo si yo pago a tiempo?",
                            "value": "¿Por qué mi puntaje es bajo si yo pago a tiempo?"
                          },
                          {
                            "text": "¿Cómo puedo mejorar mi puntaje?",
                            "value": "¿Cómo puedo mejorar mi puntaje?"
                          },
                          {
                            "text": "¿Por qué debo de invertir para subir mi puntaje?",
                            "value": "¿Por qué debo de invertir para subir mi puntaje?"
                          },
                          {
                            "text": "No estoy de acuerdo con la evaluación que me ponen",
                            "value": "No estoy de acuerdo con la evaluación que me ponen"
                          }
                        ],
                        "title": "Dudas Frecuentes"
                      }
                    }
                ],
                
            }
        return response
        
    elif event['interpretations'][0]['intent']['name']=='StartOverIntent':
        sentiment=client.detect_sentiment(Text=event['inputTranscript'],LanguageCode='es')['Sentiment']
        current_retry = int(dynamo_response['Items'][0]['current_retry'])
        current_retry = escalation_sentiment(sentiment,current_retry)
        field = 'current_retry'
        reintento = str(current_retry)
        updateDynamoDB(DYNAMO_TABLE,field,current_retry)
        response = {
                "sessionState": {
                    'sessionAttributes': {},
                    "dialogAction": {
                        "type": "ElicitIntent",
                    },
                    "intent": {
                        "name": 'StartOverIntent',
                        "state": "Fulfilled"
                    }
                },
                'messages': [ 
                    {
                    'contentType': 'PlainText',
                    'content': 'Ok empezemos de nuevo.'
                    },
                    {
                      "contentType": "ImageResponseCard",
                      "imageResponseCard": {
                        "buttons": [
                          {
                            "text": "Comenzar de nuevo",
                            "value": "Hola"
                          }
                        ],
                        "title": "Empezar de nuevo"
                      }
                    }
                ],
                
            }
        return response
        
    else:
        print(" en cualquier otra")
    
    #sentiment=client.detect_sentiment(Text=event['inputTranscript'],LanguageCode='en')['Sentiment']
    
    #return result
    
    
def fun_select(v1,v2,v3):
    return random.choice([v1,v2,v3])
    
def fun_tab_rec(value):
    if value.lower()=="uso de línea de crédito":
        resp = " mantener un consumo promedio de todas tus tarjetas de crédito por debajo del 30% para que el banco pueda ver que se esta haciendo un uso responsable de la línea de crédito. Si tienes este factor en rojo o amarillo puede ser que hayas incrementado el uso de tu línea de crédito en el último mes. Si es algo coyuntural de un mes y luego reduces la el uso de tu línea nuevamente, no te preocupes, lo importante es no permanecer con tus tarjetas al límite por mucho meses. Haciendo clic en el factor en la app podrás ver el detalle de tu consumo en cada tarjeta que tienes activa en el sistema financiero. "
        return resp
    elif value.lower()=="pago a tiempo":
        resp = " regularizar el pago pendiente en caso aún no lo hayas hecho. Recuerda que la información en la app tiene un desfase de 2 meses por lo que, si ya pagaste, en la siguiente actualización ya no debería de salir la mora; sin embargo, ten en cuenta que igual queda en tu historial esa mora. Lo mejor es procurar pagar siempre antes de la fecha límite de tu contrato para evitar contra tiempos. Si quieres ver el detalle de la empresa que reportó la mora puedes hacerlo haciendo click en el mes que figura con un aspa dentro del factor pago a tiempo. "   
        return resp
    elif value.lower()=="deuda total": 
        resp = " organizar tus finanzas para que tus ingresos mensuales puedan cubrir tanto tus gastos fijos como tus compromisos de pagos para que no te retrases. Es por eso que tu factor de pago a tiempo también se encuentra en rojo. Recuerda que en Mis Finanzas también cuentas con dos secciones donde puedes hacer seguimiento a tus gastos y asi identificar categorias donde puedes reducir un poco tus consumos. "
        return resp
    elif value.lower()=="ahorro promedio": 
        resp = " empezar a ahorrar semanal o mensualmente montos que se ajusten a tu nivel de ingresos y gastos fijos. Para encontrarte en un nivel medio en este factor necesitas contar con 350 soles promedio en los últimos 3 meses y 1,100 soles para alcanzar el nivel más alto. Recuerda que al ser un promedio diario, la manera más segura y fácil de mantener ese saldo en tus cuentas es trasladandolo a tu alcancía virtual."
        return resp
    elif value.lower()=="cuentas de inversión": 
        resp = " evaluar si estas en la capacidad de ahorrar a largo plazo con alguna de las opciones que tenemos en el banco (plazo fijo o fondos mutuos. En caso seas dependiente, también puedes trasladar tu CTS y será considerado como un ahorro de inversión. Este factor es tomado en cuenta ya que indica una buena salud financiera ya que muestra tu capacidad de mantener líquidez o efectivo para tus gastos del mes a mes a pesar de tener dinero guardado a largo plazo.  Asimismo, por regulación de la SBS los bancos no compartimos información de saldos con ninguna entidad y, a diferencia de los créditos, no podemos tomar esa información para agregarlo a tu evaluación. "
        return resp
    else:
        resp = "  "
        return resp
    

    
