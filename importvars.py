# Function to import vars from TXT file

def importVars(var):
    onevaluevars = [3, 4, 6, 7, 10, 11, 12]
    dicvars = [8, 13]
    arrayvars = [15]
    with open("vars.txt", mode="r", encoding="utf-8", newline="") as varsfile:
        lines = varsfile.readlines()
        # Return desired var
        if var in onevaluevars:
            return float(lines[var].split("=")[1])
        elif var in dicvars:
            values = lines[var].split("=")[1]
            dic = {}
            for i in values.split(","):
                j = i.split(":")
                dic[int(j[0].strip())] = float(j[1])
            return dic
        elif var in arrayvars:
            values = lines[var].split("=")[1]
            array = []
            for i in values.split(","):
                array.append(int(i))
            return array
        elif var == "regionbans":
            count = 0
            dic = {}
            for i in lines:
                count += 1
                if count >= 19:
                    parts = i.split(":")
                    key = parts[0]
                    array = []
                    for j in parts[1].split(","):
                        array.append(int(j))

                    dic[key] = array
            return dic
