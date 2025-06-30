import re

def clean_text_file(input_path, output_path, group_size=5):
    # List of phrases to remove if found in a line
    unwanted_phrases = [
        "مرورگر شما از تگ ویدئو پیشتیبانی نمی کند!",
        "Length of Course",
        "Click Here",
        "Details",
        "(14:30 - 19:30) or (9:00 - 14:00)",
        "(9:00 - 14:00)",
        "COMING SOON",
        "!",
        "Telegram",
        "Instagram",
        "Home",
        "Menu",
        "Treasure of Knowledge",
        "Departments",
        "Android",
        "FAQ",
        "رسالت ما",
        "Application:", 
        "گالری تصاویر", 
        "خدمات ما", 
        "چرا ایران-استرالیا؟", 
        "همکاری و استخدام", 
        "GRE", 
        "بانکداری", 
        "دوره آموزش زبان انگلیسی سازمانی", 
        "آپارات", 
        "دپارتمان تحقیق و نوآوری", "مدیریت", 
        "نرم افزارهای ایران-استرالیا",
        "Level", 
        "Teachers' Workshops", 
        "Useful Links", "+ Read More", "Aparat", "Programming", ":", "دپارتمان ها", 
        "همکاری ها", "استخدام کارمند", "پرسش های متداول", "Workshops", "گنجینه دانش", 
        "فارسی", "ارزش ها", "درباره ما"
        
    ]

    # Weekday names in English and Persian
    weekday_names = [
        "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
        "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه", "شنبه", "یکشنبه"
    ]

    def is_only_numbers(line):
        return line.strip().isdigit()

    def is_weekday_name(line):
        return line.strip() in weekday_names

    def is_unwanted_line(line):
        stripped = line.strip()
        if not stripped:
            return True
        if is_only_numbers(stripped) or is_weekday_name(stripped):
            return True
        return any(phrase in stripped for phrase in unwanted_phrases)

    # Read and clean lines
    with open(input_path, 'r', encoding='utf-8') as infile:
        lines = infile.readlines()

    cleaned_lines = [line.strip() for line in lines if not is_unwanted_line(line)]

    # Group into chunks
    grouped_lines = [
        ' '.join(cleaned_lines[i:i + group_size])
        for i in range(0, len(cleaned_lines), group_size)
    ]

    # Write output
    with open(output_path, 'w', encoding='utf-8') as outfile:
        for paragraph_line in grouped_lines:
            outfile.write(paragraph_line + '\n')

    print(f"Cleaned and grouped text saved to: {output_path}")

# Example usage
if __name__ == "__main__":
    clean_text_file('./cleaned_merged_output.txt', './more_cleaned_merged_output.txt')
