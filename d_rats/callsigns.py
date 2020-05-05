import re

def find_us_callsigns(string):
    extra2x1 = "[aAkKnNwW][A-z][0-9][A-z]"
    others = "[aAkKnNwW][A-z]?[0-9][A-z]{2,3}"

    regex = "\\b(%s|%s)\\b" % (extra2x1, others)

    return re.findall(regex, string)

def find_au_callsigns(string):
    regex = '\\b[Vv][Kk][0-9][Ff]?[A-z]{2,3}'

    return re.findall(regex, string)

def find_ca_callsigns(string):
    regex = '[Vv][EeAa][0-9][A-z]{2,3}'
    
    return re.findall(regex, string)

callsign_functions = {
    "US" : find_us_callsigns,
    "Australia" : find_au_callsigns,
    "Canada" : find_ca_callsigns,
}

def find_callsigns(config, string):
    list = []

    cs = eval(config.get("prefs", "callsigns"))
    enabled = [y for x,y in cs if x]

    for t in callsign_functions.keys():
        if callsign_functions.has_key(t) and t in enabled:
            list += callsign_functions[t](string)
    
    return list
