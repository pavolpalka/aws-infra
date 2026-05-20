import json
import os
from datetime import datetime
import boto3

# Inicializácia DynamoDB
dynamodb = boto3.resource('dynamodb')
table_name = os.environ.get('DYNAMODB_TABLE', 'SeminarRegistracie')
table = dynamodb.Table(table_name)

def handler(event, context):
    dnesny_datum = datetime.now().strftime("%d.%m.%Y")

    for record in event['Records']:
        try:
            # 1. Parsovanie SNS správy
            sns_message = record['Sns']['Message']
            data = json.loads(sns_message)
            
            meno = data.get('meno', '').strip()
            priezvisko = data.get('priezvisko', '').strip()
            email = data.get('email', '').strip()
            seminar_id = data.get('seminarId', '').strip()
            dni = data.get('dni', [])
            nova_poznamka = data.get('poznamka', '').strip()
            
            # Unikátny kľúč používateľa
            unique_user_key = f"{meno}-{priezvisko}-{email}".replace(" ", "").lower()
            sort_key = "PROFILE"
            
            # Kontrola flagu 'nepride' na základe aktuálnej poznámky
            nepride_flag = False
            if nova_poznamka.lower().startswith("nepride"):
                nepride_flag = True

            # 2. Načítanie existujúceho používateľa
            response = table.get_item(Key={'PK': unique_user_key, 'SK': sort_key})
            existujuci_user = response.get('Item')

            if existujuci_user:
                seminare = existujuci_user.get('seminare', {})
                
                if seminar_id in seminare:
                    # A. UPDATE existujúceho seminára
                    stary_seminar = seminare[seminar_id]
                    stara_poznamka = stary_seminar.get('poznamka', '').strip()
                    
                    if not nova_poznamka:
                        finalna_poznamka = stara_poznamka
                    else:
                        if stara_poznamka:
                            finalna_poznamka = f"{stara_poznamka} | [{dnesny_datum}]: {nova_poznamka}"
                        else:
                            finalna_poznamka = f"[{dnesny_datum}]: {nova_poznamka}"
                        
                    seminare[seminar_id] = {
                        'dni': dni,
                        'poznamka': finalna_poznamka,
                        'datum_registracie': dnesny_datum,
                        'nepride': nepride_flag
                    }
                else:
                    # B. PRIDANIE nového seminára k existujúcemu userovi
                    finalna_poznamka = f"[{dnesny_datum}]: {nova_poznamka}" if nova_poznamka else ""
                    
                    seminare[seminar_id] = {
                        'dni': dni,
                        'poznamka': finalna_poznamka,
                        'datum_registracie': dnesny_datum,
                        'nepride': nepride_flag
                    }
                
                table.update_item(
                    Key={'PK': unique_user_key, 'SK': sort_key},
                    UpdateExpression="set seminare = :s",
                    ExpressionAttributeValues={':s': seminare}
                )
                print(f"Aktualizovaný seminár {seminar_id} pre používateľa {unique_user_key}")

            else:
                # C. INSERT úplne nového používateľa
                finalna_poznamka = f"[{dnesny_datum}]: {nova_poznamka}" if nova_poznamka else ""
                
                novy_user = {
                    'PK': unique_user_key,
                    'SK': sort_key,
                    'meno': meno,
                    'priezvisko': priezvisko,
                    'email': email,
                    'seminare': {
                        seminar_id: {
                            'dni': dni,
                            'poznamka': finalna_poznamka,
                            'datum_registracie': dnesny_datum,
                            'nepride': nepride_flag
                        }
                    }
                }
                table.put_item(Item=novy_user)
                print(f"Vytvorený nový používateľ {unique_user_key} s prvým seminárom {seminar_id}")
            
        except Exception as e:
            print(f"Chyba pri spracovaní: {str(e)}")
            raise e

    return {
        'statusCode': 200,
        'body': json.dumps('Zápis do DB úspešne dokončený.')
    }