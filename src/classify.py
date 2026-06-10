def classify(score, mastery_threshold=0.8, attention_threshold=0.2):
    if score >= mastery_threshold:
        return "Mastered"
    elif score <= attention_threshold:
        return "Need Attention" 
    else:
        return "Progressing"