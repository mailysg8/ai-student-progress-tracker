def classify(score, mastery_threshold=0.8, practice_threshold=0.2):
    if score >= mastery_threshold:
        return "Mastered"
    elif score <= practice_threshold:
        return "Needs Practice" 
    else:
        return "Progressing"