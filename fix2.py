with open("frontend/src/pages/Expediente.tsx", "r") as f:
    lines = f.readlines()

idx = 474 - 1
lines.insert(idx, "    // eslint-disable-next-line @typescript-eslint/no-explicit-any\n")

with open("frontend/src/pages/Expediente.tsx", "w") as f:
    f.writelines(lines)
