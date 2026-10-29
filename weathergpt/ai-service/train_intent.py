#!/usr/bin/env python3
"""
WeatherGPT – intent classifier trainer
======================================
Trains a small, offline intent model (TF-IDF character n-grams + logistic
regression) that backs up the rule-based NLU in nlp.py.

    python train_intent.py                  # build dataset, train, evaluate, save model
    python train_intent.py --predict "kal pune mein chhata chahiye kya"
    python train_intent.py --export-only    # only write data/intent_dataset.csv
    python train_intent.py --custom data/my_questions.csv   # add your own labelled rows

Outputs
-------
    data/intent_dataset.csv        generated training data  (text, language, intent, group)
    models/intent_model.joblib     trained model (loaded automatically by nlp.py)
    models/intent_metrics.json     accuracy / per-language / per-intent report

IMPORTANT – read this
---------------------
* The seed sentences below are a STARTER set written by hand. Template-based
  augmentation makes the dataset bigger, but not more diverse. Real accuracy
  comes from adding real questions: put them in a CSV with columns
  text,language,intent (see --custom) and retrain.
* Non-English seeds (Hindi, Marathi, Tamil, Telugu, Bengali, Kannada, Malayalam,
  Gujarati) must be reviewed by native speakers.
* The reported accuracy is measured on held-out TEMPLATES (sentence patterns the
  model never saw in training), which is stricter than a random split — but it is
  still measured on my own wording. Treat it as an upper bound.
"""
import argparse
import csv
import json
import os
import random
import re
import sys
import unicodedata
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")
MODEL_DIR = os.path.join(HERE, "models")
DATASET_PATH = os.path.join(DATA_DIR, "intent_dataset.csv")
MODEL_PATH = os.path.join(MODEL_DIR, "intent_model.joblib")
METRICS_PATH = os.path.join(MODEL_DIR, "intent_metrics.json")

SEED = 42

# ─────────────────────────────────────────────────────────────────────────────
# Placeholders: {L} = place, {T} = time phrase (both optional-looking in text)
# ─────────────────────────────────────────────────────────────────────────────
LOCATIONS = {
    "en": ["Mumbai", "Delhi", "Pune", "Chennai", "Kolkata", "Bangalore", "Hyderabad", "Ahmedabad", "Jaipur",
           "Lucknow", "Nagpur", "Nashik", "Bhopal", "Patna", "Indore", "Surat", "Kochi", "Goa", "Shimla",
           "Manali", "Ooty", "Visakhapatnam", "Coimbatore", "Madurai", "Guwahati", "Bhubaneswar", "Chandigarh",
           "Dehradun", "Ranchi", "Raipur", "Mysuru", "Varanasi", "Amritsar", "Srinagar", "Shirdi", "Kolhapur"],
    "hi": ["मुंबई", "दिल्ली", "पुणे", "चेन्नई", "कोलकाता", "बेंगलुरु", "हैदराबाद", "अहमदाबाद", "जयपुर", "लखनऊ",
           "नागपुर", "नाशिक", "भोपाल", "पटना", "इंदौर", "वाराणसी", "गोवा", "शिमला", "मनाली", "देहरादून"],
    "mr": ["मुंबई", "पुणे", "नाशिक", "नागपूर", "कोल्हापूर", "औरंगाबाद", "सोलापूर", "दिल्ली", "गोवा", "सातारा"],
    "ta": ["சென்னை", "மதுரை", "கோயம்புத்தூர்", "திருச்சி", "சேலம்", "வேலூர்", "ஊட்டி"],
    "te": ["హైదరాబాద్", "విశాఖపట్నం", "విజయవాడ", "తిరుపతి", "వరంగల్", "గుంటూరు"],
    "bn": ["কলকাতা", "দিল্লি", "মুম্বই", "শিলিগুড়ি", "দার্জিলিং"],
    "kn": ["ಬೆಂಗಳೂರು", "ಮೈಸೂರು", "ಮಂಗಳೂರು", "ಹುಬ್ಬಳ್ಳಿ", "ಬೆಳಗಾವಿ"],
    "ml": ["കൊച്ചി", "തിരുവനന്തപുരം", "കോഴിക്കോട്", "തൃശ്ശൂർ"],
    "gu": ["અમદાવાદ", "સુરત", "વડોદરા", "રાજકોટ", "ગાંધીનગર"],
}
LOCATIONS["hi-Latn"] = LOCATIONS["en"]
LOCATIONS["mr-Latn"] = LOCATIONS["en"]

TIMES = {
    "en": ["today", "tomorrow", "tonight", "this weekend", "next week", "on friday", "right now", "", ""],
    "hi-Latn": ["aaj", "kal", "parso", "is hafte", "abhi", "agle hafte", "", ""],
    "hi": ["आज", "कल", "परसों", "अभी", "इस हफ्ते", "", ""],
    "mr": ["आज", "उद्या", "परवा", "आत्ता", "", ""],
    "ta": ["இன்று", "நாளை", ""],
    "te": ["ఈరోజు", "రేపు", ""],
    "bn": ["আজ", "কাল", ""],
    "kn": ["ಇಂದು", "ನಾಳೆ", ""],
    "ml": ["ഇന്ന്", "നാളെ", ""],
    "gu": ["આજે", "કાલે", ""],
}
TIMES["mr-Latn"] = ["aaj", "udya", "parva", ""]

# ─────────────────────────────────────────────────────────────────────────────
# Seed templates:  SEEDS[intent][language] = [templates]
# Keep sentences natural and varied. Add more here (or use --custom).
# ─────────────────────────────────────────────────────────────────────────────
SEEDS = {
    "current": {
        "en": ["what is the weather in {L} {T}", "{L} weather {T}", "how is the weather in {L} {T}",
               "current temperature in {L}", "tell me about the weather in {L} {T}", "weather update for {L}",
               "what's it like outside in {L} {T}", "how hot is it in {L} right now"],
        "hi-Latn": ["{L} mein {T} mausam kaisa hai", "{T} {L} ka mausam batao", "{L} ka temperature kitna hai",
                    "mausam kaisa hai {L} mein {T}", "{L} ka tapman kitna hai"],
        "hi": ["{T} {L} में मौसम कैसा है", "{L} का तापमान कितना है", "{L} का मौसम बताओ {T}", "{T} {L} का मौसम कैसा रहेगा"],
        "mr": ["{T} {L} मध्ये हवामान कसे आहे", "{L} चे तापमान किती आहे", "{L} चे हवामान सांगा {T}"],
        "ta": ["{T} {L} வானிலை எப்படி இருக்கிறது", "{L} வெப்பநிலை என்ன"],
        "te": ["{T} {L} లో వాతావరణం ఎలా ఉంది", "{L} ఉష్ణోగ్రత ఎంత"],
        "bn": ["{T} {L} এর আবহাওয়া কেমন", "{L} এর তাপমাত্রা কত"],
        "kn": ["{T} {L} ನಲ್ಲಿ ಹವಾಮಾನ ಹೇಗಿದೆ", "{L} ತಾಪಮಾನ ಎಷ್ಟು"],
        "ml": ["{T} {L} ലെ കാലാവസ്ഥ എങ്ങനെയാണ്", "{L} താപനില എത്രയാണ്"],
        "gu": ["{T} {L} માં હવામાન કેવું છે", "{L} નું તાપમાન કેટલું છે"],
    },
    "rain": {
        "en": ["will it rain in {L} {T}", "is it going to rain in {L} {T}", "chance of rain in {L} {T}", "rain in {L} {T}",
               "{L} rain {T}", "do you think it will rain {T} in {L}", "is it raining in {L} now",
               "how much rainfall is expected in {L} {T}", "will there be showers in {L} {T}"],
        "hi-Latn": ["{T} {L} mein barish hogi kya", "kya {L} mein {T} barish hogi", "{L} mein barish ho rahi hai kya",
                    "{L} barish {T}", "barish ka chance hai kya {L} mein {T}", "{L} mein kitni barish hogi {T}"],
        "hi": ["{T} {L} में बारिश होगी क्या", "क्या {L} में {T} बारिश होगी", "{L} में बारिश", "{T} {L} में कितनी बारिश होगी"],
        "mr": ["{T} {L} मध्ये पाऊस पडेल का", "{L} मध्ये पाऊस आहे का", "{T} {L} मध्ये पावसाची शक्यता आहे का"],
        "mr-Latn": ["{T} {L} madhe paus padel ka", "{L} la paus yeil ka {T}"],
        "ta": ["{T} {L} இல் மழை பெய்யுமா", "{L} இல் மழை வருமா {T}"],
        "te": ["{T} {L} లో వర్షం పడుతుందా", "{L} లో వర్షం {T}"],
        "bn": ["{T} {L} এ বৃষ্টি হবে কি", "{L} এ বৃষ্টি {T}"],
        "kn": ["{T} {L} ನಲ್ಲಿ ಮಳೆ ಬರುತ್ತದೆಯೇ", "{L} ಮಳೆ {T}"],
        "ml": ["{T} {L} ൽ മഴ പെയ്യുമോ", "{L} മഴ {T}"],
        "gu": ["{T} {L} માં વરસાદ પડશે", "{L} માં વરસાદ {T}"],
    },
    "forecast": {
        "en": ["forecast for {L} {T}", "{L} weather forecast for the next 5 days", "7 day forecast {L}",
               "weekly forecast for {L}", "what will the weather be like in {L} next week",
               "weather outlook {L} this week", "give me the 3 day forecast for {L}"],
        "hi-Latn": ["{L} ka forecast batao", "agle 5 din ka mausam {L}", "is hafte {L} mein mausam kaisa rahega",
                    "{L} ka saptahik mausam anuman", "agle 3 din ka forecast {L}"],
        "hi": ["{L} का पूर्वानुमान बताओ", "अगले 5 दिन का मौसम {L}", "इस हफ्ते {L} में मौसम कैसा रहेगा", "{L} का साप्ताहिक मौसम अनुमान"],
        "mr": ["{L} चा हवामान अंदाज सांगा", "पुढील 5 दिवस {L} चे हवामान", "या आठवड्यात {L} मध्ये हवामान कसे असेल"],
        "ta": ["{L} வானிலை முன்னறிவிப்பு", "அடுத்த 5 நாட்கள் {L} வானிலை"],
        "te": ["{L} వాతావరణ సూచన", "రాబోయే 5 రోజుల {L} వాతావరణం"],
        "bn": ["{L} এর আবহাওয়ার পূর্বাভাস", "আগামী 5 দিনের {L} এর আবহাওয়া"],
        "kn": ["{L} ಹವಾಮಾನ ಮುನ್ಸೂಚನೆ", "ಮುಂದಿನ 5 ದಿನಗಳ {L} ಹವಾಮಾನ"],
        "ml": ["{L} കാലാവസ്ഥ പ്രവചനം", "അടുത്ത 5 ദിവസത്തെ {L} കാലാവസ്ഥ"],
        "gu": ["{L} ની હવામાન આગાહી", "આગામી 5 દિવસનું {L} નું હવામાન"],
    },
    "humidity": {
        "en": ["what is the humidity in {L} {T}", "is it humid in {L} {T}", "humidity level {L}",
               "will it be muggy {T} in {L}", "how sticky is it in {L}"],
        "hi-Latn": ["{L} mein humidity kitni hai", "{L} mein umas hai kya {T}", "{T} {L} mein nami kitni rahegi"],
        "hi": ["{L} में नमी कितनी है", "{L} में उमस है क्या {T}", "{T} {L} में आर्द्रता कितनी रहेगी"],
        "mr": ["{L} मध्ये आर्द्रता किती आहे", "{L} मध्ये दमट हवामान आहे का {T}"],
        "ta": ["{L} இல் ஈரப்பதம் எவ்வளவு"], "te": ["{L} లో తేమ ఎంత ఉంది"],
    },
    "wind": {
        "en": ["how windy is it in {L} {T}", "wind speed in {L}", "will it be windy {T} in {L}",
               "is there a strong wind in {L} {T}", "wind conditions {L}"],
        "hi-Latn": ["{L} mein hawa kitni tez hai", "{T} {L} mein tez hawa chalegi kya", "{L} mein hawa ki raftaar"],
        "hi": ["{L} में हवा की रफ्तार कितनी है", "{T} {L} में तेज हवा चलेगी क्या", "{L} में हवा कैसी है"],
        "mr": ["{L} मध्ये वाऱ्याचा वेग किती आहे", "{T} {L} मध्ये जोरदार वारा वाहेल का"],
        "ta": ["{L} இல் காற்றின் வேகம் என்ன"], "te": ["{L} లో గాలి వేగం ఎంత"],
    },
    "umbrella": {
        "en": ["do I need an umbrella in {L} {T}", "should I carry an umbrella {T} in {L}", "umbrella needed in {L}",
               "will I need a raincoat in {L} {T}"],
        "hi-Latn": ["kya mujhe {T} {L} mein chhata le jana chahiye", "{L} mein chhata chahiye kya {T}",
                    "{T} chhatri leke jaun kya {L} mein"],
        "hi": ["क्या मुझे {T} {L} में छाता ले जाना चाहिए", "{L} में छाता चाहिए क्या {T}", "{T} {L} में छाता चाहिए"],
        "mr": ["{T} {L} मध्ये छत्री घ्यावी का", "{L} मध्ये छत्री लागेल का {T}"],
        "ta": ["{T} {L} இல் குடை எடுத்துச் செல்லவா"], "te": ["{T} {L} లో గొడుగు తీసుకెళ్లాలా"],
    },
    "clothing": {
        "en": ["what should I wear in {L} {T}", "do I need a jacket in {L} {T}", "should I wear a sweater {T} in {L}",
               "what clothes to pack for {L} {T}"],
        "hi-Latn": ["{T} {L} mein kya pehnu", "{L} mein jacket chahiye kya {T}", "{L} mein sweater pehanna padega kya"],
        "hi": ["{T} {L} में क्या पहनूं", "{L} में जैकेट चाहिए क्या {T}", "{L} में स्वेटर पहनना पड़ेगा क्या"],
        "mr": ["{T} {L} मध्ये काय घालू", "{L} मध्ये स्वेटर लागेल का {T}"],
    },
    "feels_like": {
        "en": ["how hot will it feel in {L} {T}", "what does it feel like outside in {L}", "feels like temperature {L}",
               "how cold is it in {L} {T}", "how hot is it really in {L} {T}"],
        "hi-Latn": ["{L} mein kitni garmi lagegi {T}", "{L} mein kitni thand hai {T}", "{T} {L} mein kitni garmi hai"],
        "hi": ["{L} में कितनी गर्मी लगेगी {T}", "{L} में कितनी ठंड है {T}", "{T} {L} में कितनी गर्मी है"],
        "mr": ["{L} मध्ये किती गरम वाटेल {T}", "{L} मध्ये किती थंडी आहे {T}"],
    },
    "fog": {
        "en": ["is there fog in {L} {T}", "visibility in {L}", "will it be foggy {T} in {L}", "dense fog in {L} {T}",
               "is it misty in {L}"],
        "hi-Latn": ["{L} mein kohra hai kya", "{T} {L} mein kohra padega kya", "{L} mein dhund hai kya {T}"],
        "hi": ["{L} में कोहरा है क्या", "{T} {L} में धुंध रहेगी क्या", "{L} में घना कोहरा {T}"],
        "mr": ["{L} मध्ये धुके आहे का", "{T} {L} मध्ये धुके पडेल का"],
    },
    "snow": {
        "en": ["will it snow in {L} {T}", "snowfall in {L}", "is there frost in {L} {T}", "will there be hail in {L}",
               "is it snowing in {L} now"],
        "hi-Latn": ["{L} mein barf giregi kya", "{T} {L} mein barfbari hogi kya", "{L} mein ole girenge kya"],
        "hi": ["{L} में बर्फबारी होगी क्या", "{L} में ओले गिरेंगे क्या {T}", "{T} {L} में बर्फ गिरेगी क्या"],
        "mr": ["{L} मध्ये बर्फ पडेल का", "{T} {L} मध्ये गारपीट होईल का"],
    },
    "heatwave": {
        "en": ["is there a heatwave in {L}", "heat wave warning {L} {T}", "is it too hot in {L} {T}",
               "is there heat stroke risk in {L}", "extreme heat in {L} {T}"],
        "hi-Latn": ["{L} mein loo chal rahi hai kya", "{L} mein heatwave hai kya", "{T} {L} mein bahut garmi hogi kya"],
        "hi": ["{L} में लू चल रही है क्या", "{L} में हीटवेव है क्या", "{T} {L} में भीषण गर्मी पड़ेगी क्या"],
        "mr": ["{L} मध्ये उष्णतेची लाट आहे का", "{T} {L} मध्ये खूप उष्णता असेल का"],
    },
    "cold_wave": {
        "en": ["is there a cold wave in {L}", "cold wave alert {L} {T}", "is it freezing in {L} {T}",
               "will it be chilly {T} in {L}", "extreme cold in {L} {T}"],
        "hi-Latn": ["{L} mein sheetlahar hai kya", "{T} {L} mein bahut thand padegi kya", "{L} mein kadake ki thand {T}"],
        "hi": ["{L} में शीतलहर है क्या", "{L} में कड़ाके की ठंड पड़ेगी क्या {T}", "{T} {L} में बहुत ठंड होगी क्या"],
        "mr": ["{L} मध्ये थंडीची लाट आहे का", "{T} {L} मध्ये खूप थंडी पडेल का"],
    },
    "thunder": {
        "en": ["will there be a thunderstorm in {L} {T}", "lightning in {L}", "is a storm coming to {L} {T}",
               "thunder and lightning {T} {L}", "any storm warning for {L} tonight"],
        "hi-Latn": ["{L} mein toofan aayega kya", "{T} {L} mein bijli girne ka khatra hai kya", "{L} mein aandhi toofan {T}"],
        "hi": ["{L} में तूफान आएगा क्या", "{T} {L} में बिजली गिरने का खतरा है क्या", "{L} में आंधी तूफान {T}"],
        "mr": ["{L} मध्ये वादळ येईल का", "{T} {L} मध्ये वीज पडेल का"],
    },
    "uv_index": {
        "en": ["what is the UV index in {L} {T}", "is the sun harmful in {L} {T}", "do I need sunscreen in {L}",
               "sunburn risk {L} {T}"],
        "hi-Latn": ["{L} mein UV index kitna hai", "{T} {L} mein dhoop tez hai kya", "{L} mein sunscreen lagana chahiye kya"],
        "hi": ["{L} में यूवी इंडेक्स कितना है", "{L} में सनस्क्रीन लगाना चाहिए क्या", "{T} {L} में धूप कितनी तेज है"],
        "mr": ["{L} मध्ये यूव्ही इंडेक्स किती आहे", "{T} {L} मध्ये ऊन किती तीव्र आहे"],
    },
    "advisory": {
        "en": ["should I spray my crops in {L} {T}", "is it good to sow wheat in {L} {T}",
               "should I irrigate my field in {L} {T}", "can I harvest {T} in {L}",
               "is it safe to go fishing in {L} {T}", "is it safe to fly in {L} {T}", "flood risk in {L} {T}",
               "should fishermen go to sea from {L} {T}", "pesticide spraying advice for {L}",
               "farming advisory for {L} {T}"],
        "hi-Latn": ["kya {T} {L} mein fasal par spray karna theek rahega", "{L} mein kheti ke liye mausam kaisa hai {T}",
                    "kya {T} {L} mein machhli pakadne jaana safe hai", "kya mujhe {T} {L} mein sinchai karni chahiye",
                    "{L} mein kataai kab karni chahiye"],
        "hi": ["क्या {T} {L} में फसल पर छिड़काव करना ठीक रहेगा", "{L} में सिंचाई करनी चाहिए क्या {T}",
               "क्या {T} {L} में मछली पकड़ने जाना सुरक्षित है", "{L} में बुवाई के लिए मौसम कैसा है", "{L} में फसल की कटाई कब करें"],
        "mr": ["{T} {L} मध्ये फवारणी करावी का", "{L} मध्ये पेरणी करणे योग्य आहे का {T}",
               "{T} {L} मध्ये मासेमारीस जाणे सुरक्षित आहे का", "{T} {L} मध्ये शेतीसाठी हवामान कसे आहे"],
        "ta": ["{T} {L} இல் பயிருக்கு மருந்து தெளிக்கலாமா"], "te": ["{T} {L} లో పంటకు మందు పిచికారీ చేయవచ్చా"],
    },
    "outdoor": {
        "en": ["is it a good day for a picnic in {L} {T}", "will the weather be fine for a wedding in {L} {T}",
               "can we play cricket outside in {L} {T}", "planning an outdoor event in {L} {T} how is the weather",
               "is it okay for a trek near {L} {T}"],
        "hi-Latn": ["kya {T} {L} mein picnic ke liye mausam achha hai", "{T} {L} mein shaadi hai mausam kaisa rahega",
                    "bachche bahar khel sakte hain kya {L} mein {T}"],
        "hi": ["क्या {T} {L} में पिकनिक के लिए मौसम अच्छा है", "{T} {L} में शादी है, मौसम कैसा रहेगा",
               "बच्चे बाहर खेल सकते हैं क्या {L} में {T}"],
        "mr": ["{T} {L} मध्ये सहलीसाठी हवामान चांगले आहे का", "{T} {L} मध्ये लग्न आहे हवामान कसे असेल"],
    },
    "jogging": {
        "en": ["is it good for a morning run in {L} {T}", "can I go jogging {T} in {L}",
               "best time to exercise outside in {L} {T}", "is it ok to cycle in {L} {T}",
               "morning walk weather in {L}"],
        "hi-Latn": ["kya {T} {L} mein subah daudna theek rahega", "{L} mein morning walk ke liye mausam kaisa hai",
                    "{T} {L} mein cycling kar sakte hain kya"],
        "hi": ["क्या {T} {L} में सुबह दौड़ना ठीक रहेगा", "{L} में मॉर्निंग वॉक के लिए मौसम कैसा है", "{T} {L} में साइकिल चला सकते हैं क्या"],
        "mr": ["{T} {L} मध्ये सकाळी धावण्यासाठी हवामान कसे आहे", "{T} {L} मध्ये फिरायला जाणे योग्य आहे का"],
    },
    "commute": {
        "en": ["will the weather affect my commute in {L} {T}", "is it safe to drive in {L} {T}",
               "how is the weather for travelling to {L} {T}", "road conditions weather {L} {T}",
               "will rain disturb my journey to {L}"],
        "hi-Latn": ["{T} {L} mein safar ke liye mausam kaisa hai", "kya {T} {L} mein gaadi chalana safe hai",
                    "{L} jaane ke liye mausam theek hai kya {T}"],
        "hi": ["{T} {L} में सफर के लिए मौसम कैसा है", "क्या {T} {L} में गाड़ी चलाना सुरक्षित है", "{L} जाने के लिए मौसम ठीक है क्या {T}"],
        "mr": ["{T} {L} ला प्रवासासाठी हवामान कसे आहे", "{T} {L} मध्ये गाडी चालवणे सुरक्षित आहे का"],
    },
    "plants": {
        "en": ["should I water my plants in {L} {T}", "will it rain enough for my garden in {L}",
               "do my plants need watering {T} in {L}", "garden watering advice for {L} {T}"],
        "hi-Latn": ["kya mujhe {T} paudhon ko paani dena chahiye {L} mein", "{L} mein bagiche ko paani dena hoga kya {T}"],
        "hi": ["क्या मुझे {T} पौधों को पानी देना चाहिए {L} में", "{L} में बगीचे को पानी देना होगा क्या {T}"],
        "mr": ["{T} झाडांना पाणी द्यावे का {L} मध्ये", "{L} मध्ये बागेला पाणी द्यावे लागेल का {T}"],
    },
    "alerts": {
        "en": ["any weather alerts for {L}", "is there a cyclone warning for {L}", "red alert in {L} {T}",
               "flood warning in {L}", "severe weather warning {L} {T}", "emergency weather alert {L}",
               "is there an orange alert in {L}", "disaster warning {L} {T}"],
        "hi-Latn": ["{L} mein koi mausam chetavani hai kya", "{L} mein chakravat ki chetavani hai kya",
                    "{L} mein baadh ki chetavani {T}", "{T} {L} mein alert hai kya", "{L} mein baadh ka khatra hai kya"],
        "hi": ["{L} में कोई मौसम चेतावनी है क्या", "{L} में चक्रवात की चेतावनी है क्या", "{L} में बाढ़ का खतरा है क्या {T}",
               "{T} {L} में अलर्ट है क्या"],
        "mr": ["{L} साठी काही हवामान इशारा आहे का", "{L} मध्ये चक्रीवादळाचा इशारा आहे का", "{L} मध्ये पुराचा इशारा {T}"],
        "ta": ["{L} க்கு வானிலை எச்சரிக்கை உள்ளதா", "{L} இல் புயல் எச்சரிக்கை"],
        "te": ["{L} కి వాతావరణ హెచ్చరిక ఉందా", "{L} లో తుఫాను హెచ్చరిక"],
        "bn": ["{L} এর জন্য আবহাওয়া সতর্কতা আছে কি", "{L} এ ঘূর্ণিঝড়ের সতর্কতা"],
        "kn": ["{L} ಗೆ ಹವಾಮಾನ ಎಚ್ಚರಿಕೆ ಇದೆಯೇ"], "ml": ["{L} ന് കാലാവസ്ഥ മുന്നറിയിപ്പ് ഉണ്ടോ"],
        "gu": ["{L} માટે હવામાન ચેતવણી છે?"],
    },
    "climate": {
        "en": ["rainfall history of {L} for the last 5 years", "average temperature in {L} over the past 10 years",
               "climate trend in {L}", "compare monsoon rainfall in {L} over the years",
               "how much did it rain in {L} last month", "annual rainfall in {L}", "historical weather data for {L}",
               "was last year hotter than normal in {L}"],
        "hi-Latn": ["{L} ki pichhle 5 saal ki barish ka record", "{L} ka mausam ka itihas",
                    "pichhle 10 saal mein {L} ka average temperature kitna raha", "{L} mein is saal kitni barish hui"],
        "hi": ["{L} में पिछले 5 साल की बारिश का रिकॉर्ड", "{L} का जलवायु इतिहास",
               "पिछले 10 साल में {L} का औसत तापमान कितना रहा", "{L} में इस साल कितनी बारिश हुई"],
        "mr": ["{L} मधील गेल्या 5 वर्षांचा पाऊस", "गेल्या 10 वर्षांत {L} चे सरासरी तापमान", "{L} मध्ये या वर्षी किती पाऊस झाला"],
        "ta": ["{L} கடந்த 5 ஆண்டுகளின் மழை பதிவு"], "te": ["{L} గత 5 సంవత్సరాల వర్షపాతం"],
    },
    "greeting": {
        "en": ["hello", "hi", "hey there", "good morning", "good evening", "who are you", "what can you do", "help me",
               "how do you work", "hi weatherGPT", "hello there", "what is this"],
        "hi-Latn": ["namaste", "namaskar", "hello bhai", "aap kaun ho", "aap kya kar sakte ho", "hi dost"],
        "hi": ["नमस्ते", "नमस्कार", "आप कौन हैं", "आप क्या कर सकते हैं", "हेलो"],
        "mr": ["नमस्कार", "तुम्ही कोण आहात", "तुम्ही काय करू शकता", "हॅलो"],
        "ta": ["வணக்கம்", "நீங்கள் யார்"], "te": ["నమస్కారం", "మీరు ఎవరు"], "bn": ["নমস্কার", "আপনি কে"],
        "kn": ["ನಮಸ್ಕಾರ"], "ml": ["നമസ്കാരം"], "gu": ["નમસ્તે"],
    },
    "thanks": {
        "en": ["thanks", "thank you so much", "thanks a lot", "thx", "great thank you", "thanks that helps",
               "ok thank you"],
        "hi-Latn": ["dhanyavad", "shukriya", "bahut bahut dhanyavad", "thanks bhai", "bahut shukriya"],
        "hi": ["धन्यवाद", "शुक्रिया", "बहुत बहुत धन्यवाद", "आपका बहुत आभार"],
        "mr": ["धन्यवाद", "खूप खूप आभार", "आभारी आहे"],
        "ta": ["நன்றி"], "te": ["ధన్యవాదాలు"], "bn": ["ধন্যবাদ"], "kn": ["ಧನ್ಯವಾದ"], "ml": ["നന്ദി"], "gu": ["આભાર"],
    },
    "bye": {
        "en": ["bye", "goodbye", "see you later", "good night", "bye bye", "ok bye", "talk to you later"],
        "hi-Latn": ["alvida", "phir milenge", "chalo bye", "tata", "chalta hoon"],
        "hi": ["अलविदा", "फिर मिलेंगे", "ठीक है बाय", "चलता हूँ"],
        "mr": ["निरोप", "पुन्हा भेटू", "बाय"],
    },
    "fallback": {
        "en": ["what is the capital of france", "tell me a joke", "book a train ticket", "play some music",
               "who won the cricket match", "what is the price of gold", "order pizza for me", "asdfgh",
               "how to cook biryani", "what is 5 plus 7", "write a poem", "translate this sentence", "who is the prime minister",
               "what time is it", "i am feeling sad", "recommend a movie", "open youtube", "qwerty zxcv"],
        "hi-Latn": ["mujhe ek joke sunao", "gaana chalao", "sone ka bhaav kya hai", "pizza order karo",
                    "biryani kaise banate hain", "cricket match kisne jeeta", "ek kavita likho", "mera naam kya hai"],
        "hi": ["मुझे एक चुटकुला सुनाओ", "गाना चलाओ", "सोने का भाव क्या है", "बिरयानी कैसे बनाते हैं", "क्रिकेट मैच कौन जीता",
               "एक कविता लिखो"],
        "mr": ["मला एक विनोद सांगा", "सोन्याचा भाव काय आहे", "बिर्याणी कशी बनवायची", "क्रिकेट सामना कोण जिंकला"],
        "ta": ["எனக்கு ஒரு நகைச்சுவை சொல்லுங்கள்"], "te": ["నాకు ఒక జోక్ చెప్పండి"], "bn": ["আমাকে একটি জোক বলুন"],
    },
}

INTENTS = sorted(SEEDS)

# Short keyword lists: teach the model the core vocabulary, so short queries like
# "pune barish" or "mumbai toofan" work. Used with patterns like "{L} {K}", "{K} {L} {T}".
KEYWORDS = {
    "current": {"en": ["weather", "temperature", "temp", "weather update", "climate now"],
                "hi-Latn": ["mausam", "tapman", "temperature"], "hi": ["मौसम", "तापमान"], "mr": ["हवामान", "तापमान"],
                "ta": ["வானிலை", "வெப்பநிலை"], "te": ["వాతావరణం", "ఉష్ణోగ్రత"], "bn": ["আবহাওয়া", "তাপমাত্রা"],
                "kn": ["ಹವಾಮಾನ"], "ml": ["കാലാവസ്ഥ"], "gu": ["હવામાન"]},
    "rain": {"en": ["rain", "rainfall", "showers", "drizzle", "raining", "will it rain", "rain chances"],
             "hi-Latn": ["barish", "baarish", "barsat", "barish hogi kya"], "hi": ["बारिश", "बरसात", "बारिश होगी"],
             "mr": ["पाऊस", "पावसाची शक्यता"], "mr-Latn": ["paus"], "ta": ["மழை"], "te": ["వర్షం"], "bn": ["বৃষ্টি"],
             "kn": ["ಮಳೆ"], "ml": ["മഴ"], "gu": ["વરસાદ"]},
    "forecast": {"en": ["forecast", "7 day forecast", "weekly forecast", "weather outlook", "5 day forecast"],
                 "hi-Latn": ["forecast", "mausam anuman", "agle 5 din ka mausam"], "hi": ["पूर्वानुमान", "मौसम का अनुमान"],
                 "mr": ["हवामान अंदाज", "अंदाज"], "ta": ["முன்னறிவிப்பு"], "te": ["వాతావరణ సూచన"], "bn": ["পূর্বাভাস"]},
    "humidity": {"en": ["humidity", "humid", "muggy"], "hi-Latn": ["umas", "humidity", "nami"], "hi": ["नमी", "उमस", "आर्द्रता"],
                 "mr": ["आर्द्रता", "दमट"], "ta": ["ஈரப்பதம்"], "te": ["తేమ"]},
    "wind": {"en": ["wind", "windy", "wind speed", "gusts"], "hi-Latn": ["hawa", "tez hawa"], "hi": ["हवा", "तेज हवा"],
             "mr": ["वारा", "वाऱ्याचा वेग"], "ta": ["காற்று"], "te": ["గాలి"], "kn": ["ಗಾಳಿ"], "ml": ["കാറ്റ്"]},
    "umbrella": {"en": ["umbrella", "raincoat", "need umbrella"], "hi-Latn": ["chhata", "chhatri"], "hi": ["छाता", "छतरी"],
                 "mr": ["छत्री"], "ta": ["குடை"], "te": ["గొడుగు"]},
    "clothing": {"en": ["jacket", "sweater", "what to wear", "clothes to pack"], "hi-Latn": ["kya pehnu", "jacket", "sweater"],
                 "hi": ["जैकेट", "स्वेटर", "क्या पहनूं"], "mr": ["स्वेटर", "काय घालू"]},
    "feels_like": {"en": ["feels like", "how hot does it feel", "how cold does it feel"],
                   "hi-Latn": ["kitni garmi lagegi", "kitni thand lagegi"], "hi": ["कितनी गर्मी लगेगी", "कितनी ठंड लगेगी"],
                   "mr": ["किती गरम वाटेल", "किती थंडी वाटेल"]},
    "fog": {"en": ["fog", "foggy", "mist", "visibility", "dense fog"], "hi-Latn": ["kohra", "dhund"], "hi": ["कोहरा", "धुंध"],
            "mr": ["धुके"]},
    "snow": {"en": ["snow", "snowfall", "frost", "hail", "snowing"], "hi-Latn": ["barf", "barfbari", "ole"],
             "hi": ["बर्फ", "बर्फबारी", "ओले"], "mr": ["बर्फ", "गारपीट"]},
    "heatwave": {"en": ["heatwave", "heat wave", "heat stroke", "extreme heat"], "hi-Latn": ["loo", "heatwave"],
                 "hi": ["लू", "हीटवेव", "भीषण गर्मी"], "mr": ["उष्णतेची लाट"]},
    "cold_wave": {"en": ["cold wave", "freezing", "extreme cold", "chilly"], "hi-Latn": ["sheetlahar", "kadake ki thand"],
                  "hi": ["शीतलहर", "कड़ाके की ठंड"], "mr": ["थंडीची लाट"]},
    "thunder": {"en": ["thunderstorm", "lightning", "thunder", "storm", "stormy weather"],
                "hi-Latn": ["toofan", "bijli", "aandhi"], "hi": ["तूफान", "बिजली", "आंधी"], "mr": ["वादळ", "वीज"],
                "ta": ["இடி மின்னல்"], "te": ["పిడుగు"]},
    "uv_index": {"en": ["uv index", "sunscreen", "sunburn", "uv"], "hi-Latn": ["uv index", "sunscreen"],
                 "hi": ["यूवी इंडेक्स", "सनस्क्रीन"], "mr": ["यूव्ही इंडेक्स"]},
    "advisory": {"en": ["spraying", "pesticide", "sowing", "irrigation", "harvest", "fishing", "flood risk", "crop advisory"],
                 "hi-Latn": ["chhidkav", "sinchai", "kheti", "machhli pakadna"], "hi": ["छिड़काव", "सिंचाई", "बुवाई", "फसल कटाई"],
                 "mr": ["फवारणी", "पेरणी", "मासेमारी", "सिंचन"]},
    "outdoor": {"en": ["picnic", "wedding", "trek", "outdoor event", "cricket match weather"],
                "hi-Latn": ["picnic", "shaadi"], "hi": ["पिकनिक", "शादी"], "mr": ["सहल", "लग्न"]},
    "jogging": {"en": ["jogging", "morning walk", "running", "cycling", "workout outside"],
                "hi-Latn": ["daudna", "morning walk"], "hi": ["दौड़ना", "मॉर्निंग वॉक"], "mr": ["धावणे", "फिरणे"]},
    "commute": {"en": ["commute", "driving", "road trip", "travel weather", "road conditions"],
                "hi-Latn": ["safar", "gaadi chalana"], "hi": ["सफर", "गाड़ी चलाना"], "mr": ["प्रवास", "गाडी चालवणे"]},
    "plants": {"en": ["watering plants", "garden watering", "plants watering"], "hi-Latn": ["paudhe", "bagicha"],
               "hi": ["पौधे", "बगीचा"], "mr": ["झाडे", "बाग"]},
    "alerts": {"en": ["alert", "weather alert", "warning", "cyclone", "red alert", "weather warning", "flood warning"],
               "hi-Latn": ["chetavani", "chakravat", "alert"], "hi": ["चेतावनी", "चक्रवात", "अलर्ट"],
               "mr": ["इशारा", "चक्रीवादळ"], "ta": ["எச்சரிக்கை"], "te": ["హెచ్చరిక"], "bn": ["সতর্কতা"],
               "kn": ["ಎಚ್ಚರಿಕೆ"], "ml": ["മുന്നറിയിപ്പ്"], "gu": ["ચેતવણી"]},
    "climate": {"en": ["rainfall history", "climate trend", "historical weather", "annual rainfall", "average temperature last 10 years",
                       "past 5 years rainfall"],
                "hi-Latn": ["mausam ka itihas", "pichhle saal ki barish"], "hi": ["जलवायु इतिहास", "पिछले साल की बारिश"],
                "mr": ["मागील वर्षांचा पाऊस", "हवामान इतिहास"]},
}
KEYWORD_PATTERNS = ["{L} {K}", "{K} {L}", "{T} {L} {K}", "{K} {L} {T}", "{K} in {L}", "{K}"]

# Slot masking: places and single-day words are replaced by <loc>/<t> so the model learns
# from the question words, not from city names.
_MASK_TIME_WORDS = [
    "today", "tomorrow", "tonight", "right now", "on friday", "aaj", "kal", "parso", "abhi", "udya", "parva",
    "आज", "कल", "परसों", "अभी", "उद्या", "परवा", "आत्ता", "இன்று", "நாளை", "ఈరోజు", "రేపు", "আজ", "কাল",
    "ಇಂದು", "ನಾಳೆ", "ഇന്ന്", "നാളെ", "આજે", "કાલે",
]
_ALPHA = r"[\w\u0900-\u0DFF]"
_PLACES = sorted({p for v in LOCATIONS.values() for p in v}, key=len, reverse=True)
_PLACE_RE = re.compile(r"(?<!" + _ALPHA + r")(" + "|".join(map(re.escape, _PLACES)) + r")(?!" + _ALPHA + r")", re.I)
_TIME_RE = re.compile(r"(?<!" + _ALPHA + r")(" + "|".join(map(re.escape, sorted(_MASK_TIME_WORDS, key=len, reverse=True))) + r")(?!" + _ALPHA + r")", re.I)


def mask_slots(text: str, extra_places=None) -> str:
    """Replace place names and day words with <loc> / <t>. extra_places: names found by nlp.py."""
    for p in sorted(extra_places or [], key=len, reverse=True):
        if p:
            text = re.sub(r"(?<!" + _ALPHA + r")" + re.escape(p.lower()) + r"(?!" + _ALPHA + r")", " <loc> ", text)
    text = _PLACE_RE.sub(" <loc> ", text)
    text = _TIME_RE.sub(" <t> ", text)
    return re.sub(r"\s+", " ", text).strip()


def prepare(text: str, extra_places=None) -> str:
    return mask_slots(simple_normalize(text), extra_places)


# ─────────────────────────────────────────────────────────────────────────────
# Text normalisation (same idea as nlp.normalize — duplicated so this file stands alone,
# but nlp.normalize is used at prediction time if available)
# ─────────────────────────────────────────────────────────────────────────────
def simple_normalize(text: str) -> str:
    t = unicodedata.normalize("NFC", text or "").lower().strip()
    t = "".join(str(unicodedata.decimal(c)) if (not c.isascii() and unicodedata.category(c) == "Nd") else c for c in t)
    t = re.sub(r"([a-z])\1{2,}", r"\1", t)
    t = re.sub(r"[?!.,;:।]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _typo(text: str, rng: random.Random) -> str:
    """Cheap typo noise for Latin-script text: drop, swap or double one letter."""
    letters = [i for i, c in enumerate(text) if c.isalpha() and c.isascii()]
    if len(letters) < 6:
        return text
    i = rng.choice(letters[1:-1] or letters)
    kind = rng.choice(["drop", "swap", "double"])
    if kind == "drop":
        return text[:i] + text[i + 1:]
    if kind == "swap" and i + 1 < len(text) and text[i + 1].isalpha():
        return text[:i] + text[i + 1] + text[i] + text[i + 2:]
    return text[:i] + text[i] + text[i:]


def expand_seeds(per_template: int = 8, seed: int = SEED):
    """Expand templates into rows. Each row keeps a 'group' id = its template, used for honest splitting."""
    rng = random.Random(seed)
    rows, gid = [], 0
    for intent in INTENTS:
        for lang, templates in SEEDS[intent].items():
            locs = LOCATIONS.get(lang) or LOCATIONS["en"]
            times = TIMES.get(lang) or TIMES["en"]
            for tpl in templates:
                gid += 1
                has_slots = "{L}" in tpl or "{T}" in tpl
                variants = set()
                tries = 0
                target = per_template if has_slots else 1
                while len(variants) < target and tries < 60:
                    tries += 1
                    text = tpl.replace("{L}", rng.choice(locs)).replace("{T}", rng.choice(times))
                    text = re.sub(r"\s+", " ", text).strip()
                    variants.add(text)
                for text in sorted(variants):
                    rows.append((text, lang, intent, gid))
                    # lower-case / no punctuation / typo versions (Latin-script only)
                    if lang in ("en", "hi-Latn", "mr-Latn"):
                        if rng.random() < 0.35:
                            rows.append((text.lower(), lang, intent, gid))
                        if rng.random() < 0.25:
                            rows.append((_typo(text.lower(), rng), lang, intent, gid))
    # keyword-style short queries (one group per keyword)
    for intent, by_lang in KEYWORDS.items():
        for lang, kws in by_lang.items():
            locs = LOCATIONS.get(lang) or LOCATIONS["en"]
            times = TIMES.get(lang) or TIMES["en"]
            for kw in kws:
                gid += 1
                variants = set()
                for pat in KEYWORD_PATTERNS:
                    if pat == "{K} in {L}" and lang != "en":
                        continue
                    for _ in range(2 if "{L}" in pat else 1):
                        text = pat.replace("{K}", kw).replace("{L}", rng.choice(locs)).replace("{T}", rng.choice(times))
                        variants.add(re.sub(r"\s+", " ", text).strip())
                for text in sorted(variants):
                    rows.append((text, lang, intent, gid))
                    if lang in ("en", "hi-Latn") and rng.random() < 0.2:
                        rows.append((_typo(text.lower(), rng), lang, intent, gid))
    return rows


def write_dataset(rows, path=DATASET_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["text", "language", "intent", "group"])
        w.writerows(rows)
    return path


def read_custom(path, start_gid=100000):
    """Read your own labelled questions. CSV columns: text,language,intent  (language optional)."""
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for i, r in enumerate(csv.DictReader(f)):
            text, intent = (r.get("text") or "").strip(), (r.get("intent") or "").strip()
            if not text or intent not in INTENTS:
                if text:
                    print(f"  skipping custom row {i + 2}: unknown intent {intent!r}", file=sys.stderr)
                continue
            rows.append((text, (r.get("language") or "xx").strip(), intent, start_gid + i))
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# Model
# ─────────────────────────────────────────────────────────────────────────────
def build_pipeline():
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import FeatureUnion, Pipeline
    feats = FeatureUnion([
        ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), sublinear_tf=True, min_df=1)),
        ("word", TfidfVectorizer(analyzer="word", ngram_range=(1, 2), sublinear_tf=True, token_pattern=r"(?u)[^\s]+")),
    ])
    clf = LogisticRegression(C=12.0, max_iter=3000, class_weight="balanced")
    return Pipeline([("features", feats), ("clf", clf)])


def train(custom_path=None, per_template=8, verbose=True):
    import joblib
    import numpy as np
    from sklearn.model_selection import StratifiedGroupKFold

    rows = expand_seeds(per_template)
    if custom_path:
        extra = read_custom(custom_path)
        rows += extra
        if verbose:
            print(f"Added {len(extra)} custom rows from {custom_path}")
    rows = list(dict.fromkeys(rows))            # drop exact duplicates
    write_dataset(rows)

    texts = [prepare(r[0]) for r in rows]
    langs = [r[1] for r in rows]
    labels = [r[2] for r in rows]
    groups = [r[3] for r in rows]

    # Honest evaluation: 5-fold cross-validation where a template / keyword never appears in both
    # the training part and the test part of a fold. Every row is predicted exactly once.
    skf = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=SEED)
    y = np.array(labels)
    classes = sorted(set(labels))
    oof = np.zeros((len(rows), len(classes)))
    for tr, te in skf.split(texts, y, groups):
        m = build_pipeline()
        m.fit([texts[i] for i in tr], y[tr])
        p = m.predict_proba([texts[i] for i in te])
        for j, c in enumerate(m.classes_):
            oof[te, classes.index(c)] = p[:, j]
    metrics = evaluate_oof(oof, classes, texts, labels, langs)
    metrics.update({
        "n_total_rows": len(rows), "n_intents": len(classes),
        "split": "5-fold cross-validation grouped by template/keyword (unseen patterns in every test fold)",
        "note": "Measured on the author's own wording; real-world accuracy will be lower. Add real questions with --custom.",
    })

    # Final model uses ALL data
    final = build_pipeline()
    final.fit(texts, labels)
    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump({"model": final, "intents": classes, "version": 2}, MODEL_PATH)
    with open(METRICS_PATH, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)

    if verbose:
        print(f"\nDataset : {len(rows)} rows, {len(classes)} intents  ->  {DATASET_PATH}")
        print(f"Model   : {MODEL_PATH}")
        print(f"\nCross-validated accuracy : {metrics['accuracy']:.1%}   macro-F1: {metrics['macro_f1']:.3f}   (n={metrics['n_test']})")
        print("\nPer language:")
        for l, v in metrics["per_language"].items():
            print(f"  {l:8} {v['accuracy']:.1%}  (n={v['n']})")
        print("\nWeakest intents (F1):")
        per = {k: v for k, v in metrics["per_intent"].items() if k in INTENTS}
        for k, v in sorted(per.items(), key=lambda kv: kv[1]["f1-score"])[:6]:
            print(f"  {k:10} F1={v['f1-score']:.2f}  (n={int(v['support'])})")
        print("\nMost common confusions:")
        for c in metrics["top_confusions"][:6]:
            print(f"  {c['expected']:10} -> {c['predicted']:10} x{c['count']}")
        print("\nConfidence threshold (use the model only when probability >= t):")
        for s_ in metrics["threshold_sweep"]:
            print(f"  t={s_['threshold']:.1f}  coverage={s_['coverage']:.0%}  accuracy_when_used={s_['accuracy_when_used']:.1%}")
        print(f"\nFull report: {METRICS_PATH}")
    return metrics


def evaluate_oof(oof, classes, texts, labels, langs):
    import numpy as np
    from sklearn.metrics import accuracy_score, classification_report, f1_score
    y = np.array(labels)
    pred = np.array(classes)[oof.argmax(axis=1)]
    conf = oof.max(axis=1)
    out = {
        "accuracy": round(float(accuracy_score(y, pred)), 4),
        "macro_f1": round(float(f1_score(y, pred, average="macro")), 4),
        "n_test": int(len(y)),
    }
    by_lang = defaultdict(lambda: [0, 0])
    for p, t, l in zip(pred, y, langs):
        by_lang[l][1] += 1
        by_lang[l][0] += int(p == t)
    out["per_language"] = {l: {"accuracy": round(c / n, 4), "n": n} for l, (c, n) in sorted(by_lang.items())}
    out["per_intent"] = classification_report(y, pred, output_dict=True, zero_division=0)
    errs = Counter((t, p) for p, t in zip(pred, y) if p != t)
    out["top_confusions"] = [{"expected": a, "predicted": b, "count": c} for (a, b), c in errs.most_common(10)]
    sweep = []
    for t in (0.3, 0.4, 0.5, 0.6, 0.7, 0.8):
        mask = conf >= t
        sweep.append({"threshold": t, "coverage": round(float(mask.mean()), 4),
                      "accuracy_when_used": round(float((pred[mask] == y[mask]).mean()) if mask.any() else 0.0, 4)})
    out["threshold_sweep"] = sweep
    out["misclassified_examples"] = [
        {"text": x, "expected": t, "predicted": p} for x, t, p in zip(texts, y, pred) if t != p][:40]
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Prediction helper (nlp.py uses the same logic)
# ─────────────────────────────────────────────────────────────────────────────
class IntentClassifier:
    def __init__(self, path: str = MODEL_PATH):
        import joblib
        blob = joblib.load(path)
        self.model = blob["model"]
        self.classes = list(self.model.classes_)

    def predict(self, text: str, top_k: int = 3, known_places=None):
        """known_places: place names already found in the text (nlp.py passes them) — they get masked."""
        proba = self.model.predict_proba([prepare(text, known_places)])[0]
        order = proba.argsort()[::-1][:top_k]
        return [(self.classes[i], float(proba[i])) for i in order]


def main():
    ap = argparse.ArgumentParser(description="Train / test the WeatherGPT intent classifier")
    ap.add_argument("--custom", help="CSV of your own labelled questions (text,language,intent)")
    ap.add_argument("--per-template", type=int, default=8, help="sentences generated per template")
    ap.add_argument("--export-only", action="store_true", help="only write data/intent_dataset.csv")
    ap.add_argument("--predict", metavar="TEXT", help="classify one sentence with the saved model")
    args = ap.parse_args()

    if args.predict:
        if not os.path.exists(MODEL_PATH):
            sys.exit("No model yet — run `python train_intent.py` first.")
        for intent, p in IntentClassifier().predict(args.predict, top_k=5):
            print(f"{intent:10} {p:.3f}")
        return
    if args.export_only:
        rows = expand_seeds(args.per_template)
        print(f"Wrote {len(rows)} rows -> {write_dataset(rows)}")
        return
    train(args.custom, args.per_template)


if __name__ == "__main__":
    main()
