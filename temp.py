def load_elo_dict(filepath):
    elo_dict = {}

    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            
            if not line:
                continue
            
            playerid, elo = line.split('|')
            
            playerid = int(playerid.strip())
            elo = int(elo.strip())
            
            elo_dict[playerid] = elo

    return elo_dict


def dict_to_php_array(d):
    lines = ["$elo = ["]
    
    for k, v in d.items():
        lines.append(f"    {k} => {v},")
    
    lines.append("];")
    
    return "\n".join(lines)


# Uso
data = load_elo_dict('preelo-2025.txt')
php_code = dict_to_php_array(data)

print(php_code)