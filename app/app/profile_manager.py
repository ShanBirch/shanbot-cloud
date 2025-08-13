import sqlite3
import datetime
import re

DATABASE_PATH = r"C:\\Users\\Shannon\\OneDrive\\Desktop\\shanbot\\app\\analytics_data_good.sqlite"


def get_db_connection():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def add_bio_column_to_users():
    """Adds a 'bio' column to the 'users' table if it doesn't already exist."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN bio TEXT")
        conn.commit()
        print("Added 'bio' column to 'users' table.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("'bio' column already exists in 'users' table.")
        else:
            print(f"An error occurred while adding bio column: {e}")
            # raise # Optionally re-raise
    finally:
        if conn:
            conn.close()


def update_user_bio(ig_username, new_bio):
    """Updates the bio for a given Instagram username."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE users SET bio = ? WHERE ig_username = ?", (new_bio, ig_username))
        conn.commit()
        if cursor.rowcount == 0:
            print(
                f"No user found with Instagram username: {ig_username}. Bio not updated.")
            return False
        else:
            print(f"Bio updated for {ig_username}.")
            return True
    except sqlite3.Error as e:
        print(f"An error occurred while updating bio for {ig_username}: {e}")
        return False
    finally:
        if conn:
            conn.close()


def get_conversation_history(ig_username):
    """Retrieves all messages for a given Instagram username, ordered by timestamp."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT timestamp, message_type, message_text, type, text 
            FROM messages 
            WHERE ig_username = ? 
            ORDER BY timestamp ASC
        """, (ig_username,))
        messages = cursor.fetchall()
        if not messages:
            # print(f"No conversation history found for {ig_username}.") # Less verbose
            return []

        # Convert to standardized format using new unified columns
        formatted_messages = []
        for row in messages:
            timestamp, new_type, new_text, old_type, old_text = row

            # Use new columns first, fall back to old columns
            final_type = new_type if new_type is not None else old_type
            final_text = new_text if new_text is not None else old_text

            if final_text is not None and final_text.strip():
                formatted_messages.append({
                    "timestamp": timestamp,
                    "type": final_type,
                    "text": final_text
                })

        return formatted_messages
    except sqlite3.Error as e:
        print(
            f"An error occurred while retrieving conversation history for {ig_username}: {e}")
        return []
    finally:
        if conn:
            conn.close()


def add_conversation_message(ig_username, message_type, message_text, timestamp_obj):
    """Adds a new message to the messages table for a given Instagram username."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Ensure timestamp is in the correct string format for the database
    if isinstance(timestamp_obj, datetime.datetime):
        timestamp_str = timestamp_obj.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    elif isinstance(timestamp_obj, str):
        timestamp_str = timestamp_obj  # Assume it's already correctly formatted if a string
    else:
        print(
            f"Invalid timestamp type for message: {message_text}. Must be datetime or string.")
        return False

    try:
        cursor.execute(
            "SELECT 1 FROM users WHERE ig_username = ?", (ig_username,))
        if cursor.fetchone() is None:
            print(
                f"User {ig_username} not found in 'users' table. Cannot add message: '{message_text[:50]}...'")
            return False

        cursor.execute("INSERT INTO messages (ig_username, timestamp, type, text) VALUES (?, ?, ?, ?)",
                       (ig_username, timestamp_str, message_type, message_text))
        conn.commit()
        # print(f"Message added for {ig_username} at {timestamp_str}") # Less verbose
        return True
    except sqlite3.Error as e:
        print(
            f"An error occurred while adding message for {ig_username} ('{message_text[:50]}...'): {e}")
        conn.rollback()
        return False
    finally:
        if conn:
            conn.close()


def add_user_if_not_exists(ig_username, subscriber_id, initial_bio=""):
    """Adds a user if they don't exist, or updates subscriber_id/bio if they do."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT subscriber_id, bio FROM users WHERE ig_username = ?", (ig_username,))
        user_exists = cursor.fetchone()
        if user_exists:
            print(f"User {ig_username} already exists.")
            # Optionally update subscriber_id or bio if needed
            current_subscriber_id = user_exists['subscriber_id']
            current_bio = user_exists['bio']
            updated_fields = {}
            if subscriber_id and str(current_subscriber_id) != str(subscriber_id):
                updated_fields['subscriber_id'] = subscriber_id
            if initial_bio and not current_bio:  # Only update bio if it's currently empty
                updated_fields['bio'] = initial_bio

            if updated_fields:
                set_clause = ", ".join(
                    [f"{field} = ?" for field in updated_fields.keys()])
                values = list(updated_fields.values()) + [ig_username]
                cursor.execute(
                    f"UPDATE users SET {set_clause} WHERE ig_username = ?", tuple(values))
                conn.commit()
                print(
                    f"Updated existing user {ig_username} with: {updated_fields}")
            return True  # User already exists or was updated
        else:
            cursor.execute("INSERT INTO users (ig_username, subscriber_id, bio) VALUES (?, ?, ?)",
                           (ig_username, subscriber_id, initial_bio))
            conn.commit()
            print(
                f"User {ig_username} added successfully with subscriber ID {subscriber_id}.")
            return True
    except sqlite3.Error as e:
        print(
            f"An error occurred while adding/updating user {ig_username}: {e}")
        conn.rollback()
        return False
    finally:
        if conn:
            conn.close()


def parse_log_timestamp(timestamp_str, last_known_date_obj, current_year):
    """
    Parses varied timestamp formats from the log.
    - "DD Mon YYYY, HH:MM" (e.g., "5 Apr 2025, 12:42")
    - "DayOfWeek, HH:MM" (e.g., "Monday, 04:56") - relative to last_known_date_obj
    - "Today, HH:MM" (e.g., "Today, 10:39") - relative to last_known_date_obj
    Returns a datetime object or None.
    """
    timestamp_str = timestamp_str.strip()

    # Try "DD Mon YYYY, HH:MM"
    try:
        return datetime.datetime.strptime(timestamp_str, "%d %b %Y, %H:%M")
    except ValueError:
        pass

    # Try "DayOfWeek, HH:MM" or "Today, HH:MM"
    # These need a reference date (last_known_date_obj)
    if last_known_date_obj:
        time_part_match = re.search(r"(\d{2}:\d{2})$", timestamp_str)
        if not time_part_match:
            return None  # Cannot parse time

        time_obj = datetime.datetime.strptime(
            time_part_match.group(1), "%H:%M").time()

        if "Today" in timestamp_str:
            return datetime.datetime.combine(last_known_date_obj.date(), time_obj)

        days_of_week = ["Monday", "Tuesday", "Wednesday",
                        "Thursday", "Friday", "Saturday", "Sunday"]
        for i, day_name in enumerate(days_of_week):
            if day_name in timestamp_str:
                # Calculate the date of the next occurrence of this day of the week
                days_ahead = (i - last_known_date_obj.weekday() + 7) % 7
                if days_ahead == 0:  # If it's the same day of the week, assume next week unless time is later
                    current_log_time_dt = datetime.datetime.combine(
                        last_known_date_obj.date(), time_obj)
                    if current_log_time_dt > last_known_date_obj:
                        days_ahead = 0  # it is the same day
                    else:  # if the time is earlier or same, it means it's next week's day
                        days_ahead = 7

                target_date = last_known_date_obj.date() + datetime.timedelta(days=days_ahead)
                return datetime.datetime.combine(target_date, time_obj)

    # Try "Month Day, HH:MM" (assuming current year if not specified in log before)
    try:
        dt_obj = datetime.datetime.strptime(timestamp_str, "%b %d, %H:%M")
        return dt_obj.replace(year=current_year)
    except ValueError:
        pass

    print(f"Could not parse timestamp: {timestamp_str}")
    return None


def parse_conversation_log(log_str):
    """Parses the multi-line conversation log string."""
    messages = []

    # Regex to find timestamps, broadly. Specific parsing happens in parse_log_timestamp
    # This regex looks for lines that likely start a new message entry.
    # It tries to capture (Date-like part, Name-like part (optional), Text)
    # Split by lines that look like timestamps or sender lines
    # Example patterns: "5 Apr 2025, 12:42", "Shannon:", "Shane:", "Monday, 04:56"
    # The core idea is to split the log into chunks, where each chunk starts with a timestamp.

    # Pre-normalize sender names in the log string for easier regex
    log_str = re.sub(r"\\bSHane\\b", "Shane", log_str, flags=re.IGNORECASE)
    log_str = re.sub(r"\\bShann(o|oo|a)n\\b", "Shannon",
                     log_str, flags=re.IGNORECASE)

    # Split log into potential message entries. An entry starts with a timestamp.
    # Timestamps can be: "5 Apr 2025, 12:42", "Today, 10:39", "Monday, 04:56"
    # We'll use a regex that looks for these patterns at the START of a line.
    # (?m) is for multi-line mode.
    entry_splits = re.split(
        r"(?m)^((?:\d{1,2}\s\w{3}\s\d{4},\s\d{2}:\d{2})|(?:(?:Today|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s\d{2}:\d{2}))", log_str)

    raw_entries = []
    current_timestamp_str = None
    for i, part in enumerate(entry_splits):
        part = part.strip()
        if not part:
            continue
        # If part is a recognized timestamp by the split regex
        if i % 2 == 1:  # The timestamp itself
            current_timestamp_str = part
        elif current_timestamp_str:  # The text content after a timestamp
            raw_entries.append(
                {"timestamp_str": current_timestamp_str, "content": part})
            current_timestamp_str = None  # Reset for the next timestamp
        # Content before the first timestamp (should not happen with good logs)
        elif not raw_entries and part:
            print(
                f"Warning: Content found before first timestamp: {part[:100]}")

    last_known_full_date_obj = None
    current_message_year = datetime.datetime.now().year  # Default to current year

    parsed_messages = []

    for entry in raw_entries:
        timestamp_str = entry["timestamp_str"]
        content_block = entry["content"].strip()

        # Try to determine the year from the first absolute date encountered
        if not last_known_full_date_obj:
            match_year = re.search(r"(\d{4})", timestamp_str)
            if match_year:
                current_message_year = int(match_year.group(1))

        # Update last_known_full_date_obj if the current timestamp_str is a full date
        try_full_date = parse_log_timestamp(
            timestamp_str, None, current_message_year)  # Try parsing as absolute first
        if try_full_date and try_full_date.year != 1900:  # strptime default for %b %d, %H:%M
            last_known_full_date_obj = try_full_date
            # Update current year from this timestamp
            current_message_year = try_full_date.year

        # Parse the timestamp using the best available date context
        timestamp_obj = parse_log_timestamp(timestamp_str, last_known_full_date_obj if last_known_full_date_obj else datetime.datetime(
            current_message_year, 1, 1), current_message_year)

        if not timestamp_obj:
            print(
                f"Skipping entry due to unparsable timestamp: {timestamp_str} with content: {content_block[:50]}")
            continue

        # Now, parse sender and text from content_block
        lines = content_block.split('\\n')
        current_sender = None
        current_text_lines = []

        for line in lines:
            line_strip = line.strip()
            if not line_strip:
                continue

            sender_match = re.match(
                r"^(Shannon|Shane):(.*)", line_strip, re.IGNORECASE)
            if sender_match:
                if current_sender and current_text_lines:  # Save previous message part
                    parsed_messages.append({
                        "timestamp": timestamp_obj,  # Timestamp applies to all parts of this block
                        "sender_tag": current_sender.lower(),
                        "text": "\\n".join(current_text_lines).strip()
                    })
                    current_text_lines = []  # Reset for new sender part

                current_sender = sender_match.group(1)
                message_content = sender_match.group(2).strip()
                if message_content:
                    current_text_lines.append(message_content)
            elif current_sender:  # Line belongs to the current sender
                current_text_lines.append(line_strip)
            else:  # Line without explicit sender, assume Shannon if at start of block
                # This happens for messages like "Big week bro, ready for it?"
                if not current_sender and not parsed_messages:  # Or if no sender established yet for this block
                    current_sender = "Shannon"
                    current_text_lines.append(line_strip)
                elif not current_sender and parsed_messages and parsed_messages[-1]["timestamp"] == timestamp_obj:
                    # If previous message was same timestamp, assume it's continuation or Shannon default
                    current_sender = "Shannon"
                    current_text_lines.append(line_strip)
                else:
                    # If already have text for current_sender, append to it
                    if current_text_lines:
                        current_text_lines.append(line_strip)
                    else:
                        # Default to Shannon if no sender context yet in this block
                        current_sender = "Shannon"
                        current_text_lines.append(line_strip)

        if current_sender and current_text_lines:  # Add the last collected message part for this timestamp
            parsed_messages.append({
                "timestamp": timestamp_obj,
                "sender_tag": current_sender.lower(),
                "text": "\\n".join(current_text_lines).strip()
            })

        # Update last_known_full_date_obj if this timestamp was a full date
        if timestamp_obj.year != 1900:  # check if it was properly parsed with a year
            last_known_full_date_obj = timestamp_obj

    # Sort messages by timestamp just in case parsing order got mixed up (shouldn't with current logic)
    parsed_messages.sort(key=lambda x: x["timestamp"])
    return parsed_messages


def process_user_and_history(ig_username, subscriber_id, conversation_log_str, user_bio=""):
    """Adds user, parses their conversation log, and adds messages to DB."""
    print(f"Processing user: {ig_username}")
    if not add_user_if_not_exists(ig_username, subscriber_id, user_bio):
        print(
            f"Failed to add or verify user {ig_username}. Aborting history processing.")
        return

    print(f"Parsing conversation log for {ig_username}...")
    parsed_log = parse_conversation_log(conversation_log_str)

    if not parsed_log:
        print(f"No messages parsed from log for {ig_username}.")
        return

    print(f"Adding {len(parsed_log)} messages to database for {ig_username}...")
    messages_added_count = 0
    for msg_data in parsed_log:
        sender_tag = msg_data["sender_tag"]
        # Define who is 'client' and who is 'user' in the conversation
        # Assuming Shannon is the coach/client in this context, Shane is the user
        message_type = 'client' if sender_tag == 'shannon' else 'user'

        if add_conversation_message(ig_username, message_type, msg_data["text"], msg_data["timestamp"]):
            messages_added_count += 1

    print(
        f"Successfully added {messages_added_count} out of {len(parsed_log)} messages for {ig_username}.")


def parse_dialogue_log_sequential_timestamps(log_str, base_timestamp):
    """Parses a dialogue-only log, assigning sequential timestamps."""
    parsed_messages = []
    current_timestamp = base_timestamp

    # Normalize sender names for consistent matching
    log_str = re.sub(r"\bKel\b", "Kel", log_str, flags=re.IGNORECASE)
    log_str = re.sub(r"\bKristy\b", "Kristy", log_str, flags=re.IGNORECASE)
    log_str = re.sub(r"\bShann(o|oo|a)n\b", "Shannon",
                     log_str, flags=re.IGNORECASE)

    current_sender_tag = None
    current_text_lines = []
    log_lines = log_str.split('\n')

    for line_content in log_lines:
        line_strip = line_content.strip()
        if not line_strip:
            continue

        # Check if the line starts with a known sender pattern
        sender_match = re.match(
            r"^(Shannon|Kel|Kristy):\s*(.*)", line_strip, re.IGNORECASE)

        if sender_match:
            if current_sender_tag and current_text_lines:
                parsed_messages.append({
                    "timestamp": current_timestamp,
                    "sender_tag": current_sender_tag.lower(),  # Ensure lowercase for consistency
                    "text": "\n".join(current_text_lines).strip()
                })
                current_text_lines = []
                current_timestamp += datetime.timedelta(seconds=1)

            current_sender_tag = sender_match.group(
                1).lower()  # Store sender as lowercase
            message_part = sender_match.group(2).strip()
            if message_part:
                current_text_lines.append(message_part)
        elif current_sender_tag:
            current_text_lines.append(line_strip)
        else:
            print(
                f"Warning: Line '{line_strip[:50]}...' found before any sender identified. Assigning to 'shannon'.")
            current_sender_tag = "shannon"
            current_text_lines.append(line_strip)

    if current_sender_tag and current_text_lines:
        parsed_messages.append({
            "timestamp": current_timestamp,
            "sender_tag": current_sender_tag.lower(),  # Ensure lowercase for consistency
            "text": "\n".join(current_text_lines).strip()
        })

    return parsed_messages


def process_user_with_dialogue_log(ig_username, subscriber_id, dialogue_log_str, user_bio=""):
    """Adds user, parses their dialogue log with sequential timestamps, and adds messages."""
    print(f"\nProcessing user with dialogue log: {ig_username}")
    if not add_user_if_not_exists(ig_username, subscriber_id, user_bio):
        print(
            f"Failed to add or verify user {ig_username}. Aborting history processing.")
        return

    print(f"Parsing dialogue log for {ig_username}...")
    base_ts = datetime.datetime.utcnow()
    parsed_dialogue = parse_dialogue_log_sequential_timestamps(
        dialogue_log_str, base_ts)

    if not parsed_dialogue:
        print(f"No messages parsed from dialogue log for {ig_username}.")
        return

    print(
        f"Adding {len(parsed_dialogue)} messages to database for {ig_username} from dialogue log...")
    messages_added_count = 0
    for msg_data in parsed_dialogue:
        sender_tag = msg_data["sender_tag"]
        message_type = 'client' if sender_tag == 'shannon' else 'user'

        if add_conversation_message(ig_username, message_type, msg_data["text"], msg_data["timestamp"]):
            messages_added_count += 1

    print(
        f"Successfully added {messages_added_count} out of {len(parsed_dialogue)} messages for {ig_username} from dialogue log.")


if __name__ == '__main__':
    add_bio_column_to_users()
    print("\nProfile manager script initialized and bio column checked/added.")

    # --- Process Shane Minahan (Timestamped Log) ---
    shane_ig = "shane_minahan"
    shane_sub_id = "625063351"
    shane_bio = "Client focused on fitness and meal planning."
    shane_conversation_log = """\
5 Apr 2025, 12:42
Shannon: Hey Bro! Hows the week been?
6 Apr 2025, 16:21
Shane: Hey mate. It's been ok not as good as I would of liked. I have changed roaster again to just trying to get back in a routine and also getting to know the new work out

Shannon: Yeah that makes sense mate, changing rosters always messes with routine hey. How are you finding the new exercises in the program?

7 Apr 2025, 19:22
Shane: They are good, I can feel them work different areas. I'll start to ramp them up this week now im more comfortable with them. I do think I need to change and find two or three different t meals im starting to get￼ over the same two

8 Apr 2025, 06:21
Shannon: For sure bro that happens! What are you eating currently?
Good to hear your ramping them up. How can we keep that motivation going? Do the messages from me help?
8 Apr 2025, 20:34
Shane: I'm still eating the same chicken, broccoli and rice or mince, broccoli and sweet potato mash 
snack -apple and yogurt- protein shack
Eggs, avocado and a wrap or toast for breakfast. 

The breakfast im still good with I'll just look at changing up the main meals.
Do I keep the same calories and macros ?
The msg do help keep it keeps a thinking about it and striving to do better

9 Apr 2025, 07:57
Shannon: Nice one bro!
Might be time to go through some meals then hey
Wana try make pizza for dinner?
9 Apr 2025, 11:18
Shane: Yeah that sound good to me

Shannon: Aight nice
So here's your high protein options for it
Add some meat, track it in your fitness tracker and compare it to the meals your currently eating and let me know how you go
How about pasta for lunch?
12 Apr 2025, 06:47
Shannon: How was the pizza dude
16 Apr 2025, 09:22
Shane: Thanks for this mate. I will try it this week, last week I had already completed all my meal prep

16 Apr 2025, 10:02
Shannon: All g dude, let's spend the next few weeks discovering some meals hey, there's a few high protein ingredients we can go through.
16 Apr 2025, 22:02
Shane: Ok sounds good I'll do another big push on my eating and make sure I hit the targets more

17 Apr 2025, 07:17
Shannon: lets do it bro! send us a piccy of your pizza plz

22 Apr 2025, 21:13
Shane: They didn't have the base you said to get so I just used a keto wrap

23 Apr 2025, 06:49
Shannon: Yewwww
Get the base, it doesn't fall apart
How was it?
24 Apr 2025, 16:22
Shane: It was really good and not as high is cal as I thought it would of been. I will the coles and Woolworth is pretty crap out where I'm working

24 Apr 2025, 17:33
Shannon: Awesome bro
Can you get this pasta out there?

24 Apr 2025, 19:42
Shane: Yeah I have seen them
Shannon: Nice one bro! Grab those with some lean mince and some of that cheese! That's a super high protein meal
Shane: Sweet I'll add that as a couple of meal next week. It is will work for lunch's

Shannon: Nice one bro!
Send me a pic when you have!
29 Apr 2025, 18:26
Shane: Pasta made last night
I add some zucchini and carrot in as well

Shannon: Beauty!
Good macros?
Shane: It was a nice chance

Shannon: What was the protein carb fat ratio?
Shane: Sorry I had to separate out my two lunch's

Shannon: How nice is that!
Shane: Yeah it was good and having pizza as well it's a nice change up

Shannon: Beauty!
Do we try another one this coming week?
Shane: Yeah if we can please. It's making me think more about my food again and getting a little excited about eating lunch's again

Shannon: Love it
Okay! So think what you had on your pizza, but mashed sweet potato as the base
Sweet potato, veggies, chicken, high protein cheese, nandas sauce, salt! This has been my dinner for a few months now! Love it!
29 Apr 2025, 19:57
Shane: Yeah nice roughy what grams per item would I be looking at doing.

Shannon: Mhmm
I dunno
Have like 500-600 grams of potato I rekon
Its pretty low in carbs
Maybe 150 g if chicken
Or kangaroo sausage
N then
As much cheese as you want
Shane: Sweet I'll give it a go and see how that look with other meal and I might balance it out with my day time meals

Shannon: Aweosme bro
It gets pretty easy pretty quickly
Your killing it!
Shane: Thanks mate feeling heaps better for it.

Shannon: Yew
30 Apr 2025, 17:46
Shannon: Hows the training go today bro?
4 May 2025, 15:01
Shane: Hey mate sorry last week was a week for late meeting. Trained really good last week couple of late night ones but I worth doing that. Iv been better on food this week and it's bad a different in how I feel and grabbing

4 May 2025, 16:02
Shannon: No worries bro! Good to go hear your doing well! We chatted Tuesday anyway! I'll send you a buzz Wednesday looking for that next meal!
5 May 2025, 18:56
Shane: Sounds good. Could I please get the the next lot of exercises load in. Are we changing it up again or keeping ￼it the same for the last 6weeks ?

5 May 2025, 21:01
Shannon: Easy bro! Sorry should of had that ready for ya! Will get it done first thing in the morning! You can always click the kettle bell icon and grab the most recent workout, if your in the gym in early!
6 May 2025, 13:09
Shannon: Your all set up bro! Sorry that took me half the morning!
Let me know if you need adjustments!
6 May 2025, 17:32
Shane: All good just finished work so will go hit it up tonight

7 May 2025, 05:02
Shannon: Sweet
7 May 2025, 16:17
Shannon: Yo yo! Hows the week been bro? Did you get a sesh in?
8 May 2025, 19:55
Shane: Hey mate. Yeah I trained last for the first time on the new program. I can feel the burn (good burn) with the 3 set of 12 reps now. Food been going good this week I'm a lot happier with that. 
I've even got the hold family eat clean for the next 6 weeks with me so that should help me drop to around the 86kg mark

8 May 2025, 22:48
Shane: Dumbbell 21 hurt

9 May 2025, 05:35
Shannon: Love to hear it bro!
Make that sweet potato meal for me plz, then I'll hook you up with another meal
12 May 2025, 07:53
Shannon: Big week ahead bro! You ready for it?
12 May 2025, 17:16
Shane: Hey mate. Yeah it is got some big bosses from Spain over a few late nights this week. ￼
Keen to do a full week of training as I missed two days last week m.

12 May 2025, 18:28
Shane: Hey mate do you mind checking my work out out ? 
it doesn't look the same set out as the last two works our with muscle groups. I've got cable crunches in chest day and it's different to last weeks chest day. 
All good if you have set it up this way I'm just checking

12 May 2025, 20:04
Shane: Hey bro! I was going through your account and I accidentally deleted your program! 😂 Sorry bro! Any exercises you want in there that I can't throw back in?

Shane: Hey mate. Yeah it is got some big bosses from Spain over a few late nights this week. ￼ Keen to do a full week of t...
Shannon: Make it happen!n
Can throw back in** -

Shane: Haha all good mate it happens some times. Can we put these two back in they ￼ hurt, but we're good

Shannon: Will do now!
21s?
Done!
Shane:  I think they are still in there but if not yes please they suck lol

Shannon: All g! There on shoulder day I just checked!
14 May 2025, 19:33
Shannon: Yewwwwww!!
Solid effort bro!
Shane: I made the sweet potatoes bowl

Shannon: Crazy good macros
Shane: Yeah and filling as well

Shannon: Meal prep for the next few days?
Shane: It's been my lunches. Yeah I did it Monday night so it will be lunch for the week

Shannon: Solid effort bro
Bosses down yet?
Shane: Yeah they left today so things should ease up a little for the rest for the week.

Shannon: Ahh beauty
Make it to the gym this week still?
Here we go next weeks meal! This is a funny one I have sometimes.
Konjac noodles are extremely low in calories, you gotta rinse them really hard. Then you take the migoreng seasoning out of the migoreng, and add them to ya konjac noodles, chicken + veggies. Super low carb meal. Can have heaps of it!
14 May 2025, 20:12
Shane: Ok sweet it look interesting. What veg go well with it. 
 Yeah I have made the gym every day this week. Last night was a hard one I didn't feel it at all and was yawning 🥱 the entire time but still pushed through.

Shannon: Good to hear man!
Capsicum, onion, broccoli, carrots
Asian style veggies
Sweet sound good me. Lunch or dinner next week sort now

Shannon: Beauty dude!
Hows the weight moving?
Shane: Slowly I would say I'm down to 89kgs now so I'll see what Monday weight looks like and go from there

Shannon: Good one!
Slow and steady is all g! Just gotta keep making these meals, keep training, stay consistent. You'll kill it!
Shane: It's funny because this last couple of weeks the scale don't seem to me moving much but the belt is down two hole in the last 4 weeks

Shannon:L That's awesome man!
The scales are funny man there just a good tool, not the whole picture
Shane: Yeah I have been judging off clothes, scale and weekly check in pic and I'm very happy with it. I just want to get rid of some more belly fat and I'll be very happy. 
I keep telling my self I got this way over 4 year so its not just going to fall off in 12-18 weeks

Shannon: For sure man
You just gotta do it forever now so you got all the time in the world
14 May 2025, 20:55
Shane: That's very true I'm not going back to how I was

15 May 2025, 05:45
Shannon: for sure dude! gotta stay on!
Monday, 04:56
Shannon: Big week bro, ready for it?
Wednesday, 17:42
Shannon: Hows the week bro? Where's my noodles?
Today, 10:39
Shane: Hey mate. The weeks been shit. I had such a good week last week. On top of my food and training and this week I have been pumped by the works and more hobnobs from Spain. So I'm on my muscle Chef meal this week just trying to keep some control. So noodle next week and training over the weekend as I have two day to catch up on training.

Shannon: Thanks for the reply bro! you off to spain soon? Yeah nice one man, good to see you keeping up the muscle chef meals! Easy man easy, make it happen!
Shane: Thanks for the check in, It's good for me to as it keeps me moving lol. 
No I don't get to go to Spain they just keep coming to visit site as we are starting to finish up the push is on to get it done faster

Shannon: How good man how good!
Ahhh okay fair fair
Oh well bro, try to be fluid with it! Work can suck for fitness but your on a roll now, you'll make it happen!
"""  # Ending triple quotes for Shane's log

    # print(f"\nAttempting to add user '{shane_ig}' and process their conversation history.")
    # process_user_and_history(shane_ig, shane_sub_id, shane_conversation_log, shane_bio)
    # print(f"\nFinished processing for {shane_ig}.")

    # --- Process Kel (Dialogue Log) ---
    kel_ig = "kelstar"
    kel_sub_id = "647111436"
    kel_bio = "Client focused on body fat reduction and consistent training."

    kel_dialogue_log = """\
Shannon: Good Morning! You all prepared for tomorrow?
Kel: Yep! Going to smash it.
Shannon: Beautiful!!
Food ready?
Kel: I will be taking Saturdays off though. Only because I have some events on. But I won't be going crazy.
Kel: Food prep this arvo
Shannon: That's all good!
Nice one!
Did you tell me your goal weight? I can throw it in the app
Kel: Not much weight but I want my body fat to be below 40.
Shannon: Body fat % ?
Kel: Yep
Shannon: Okay great! What is it now?
Kel: 42.34%
Shannon: Okay cool!
How are you testing it? A scan?
Kel: I have the scales that tells you all of the details
Shannon: Ahh perfect!
Kel: So I've linked that to the app
Kel: The app is amazing btw
Shannon: You got this kel!
Kel: Thanks!
Shannon: Can you link your scales up to the app?
Kel: Oh yeah I have
Shannon: Beauty!!
Kel: Watch linked, fitness pal linked, scales linked - ready to go!
Shannon: Ready to rumble! Aight enjoy your Sunday! Message me tomorrow after the gym! 🙏🙏
Kel: ❤
Kel: And thanks again
Shannon: I'm glad to be apart of it!
Shannon: Hows the week been kel? Getting it done?
Kel: Yes!!! Loving it. The Arnold press got me good.
Kel: Also the consistency of my meal plan is making it so easy
Shannon: Awesome! 💯
You tracking your cals or just going off the meal plan? Does really matter either way
Doesn't*
Kel: Both so I know I'm sure I'm hitting the protein
Shannon: Awesome! Killing it!
Kel: I remembered from last time that I thought I was but I wasn't. So really dialling it in.
Shannon: Yeah awesome!
It's pretty tricky hey!
Feeling satisfied with your food at the end of the day?
Kel: It is. More so surprising that I thought I knew but I didn't.
Kel: Yeah totally. And knowing I can go off plan a bit on Saturday is brilliant for the mindset.
Shannon: Yeah that's good
It's always nice to have a chill day hey
Kel: Absolutely.
Shannon: How often are you jumping in the scales?
Kel: Probably too often
Shannon: Yeah okay
Thatl make the weight drop fast
As long as it doesn't do your head in when it goes up randomly
Kel: Well that's the trick right
Shannon: Yeah
Water weight can be random
But your all g as long as you know that
And just stay positive
Kel: It can be but I'll be honest. The past few weeks mine has been from eating shit!
Shannon: Yeah for sure
Good your honest about it
Hows everything else?
Kel: At the moment. Pretty good. Exercise is never an issue. It helps keep my head in check and I love it. Trying to get more sleep and more water in.
Shannon: Yeah awesome
How much sleep you getting?
Kel: I aim for 7 hours
Kel: More on weekends
Shannon: Yep
That's should be enough
You wake up in the middle of the night?
Kel: Not resllt
Kel: Really
Shannon: Good good!
Awesome!! Good to hear it's going well!
Kel: Yeah. It's awesome. Thank you!
Shannon: Pleasure
Kel: One of the best things I've ever done for my health
Shannon: Hey I wouldn't mind it if you tried to make a pizza for me this week. Rekon you can do that? High protein base + high protein cheese
Kel: Love a high protein pizza. I usually make mine with broccoli and chicken. It's the bomb.
Shannon: Awesome!
Kel: What kind of macros we talking?
Shannon: Just make it fit your cals for the day.
Ingredients like this tho
Kel: That's what I use anyway 🙌
Kel: That cheese is awesome
Shannon: Perfect! Cook it up for me this week plz
Kel: So pricey but worth it for a try!
Kel: Yeah awesome. Friday night.
Shannon: Beauty!!
Aight have a good night! Glad to hear your getting it!
Kel: Leg Day 2 was a killer!
Shannon: Good 🧑‍🏭🧑‍🏭🧑‍🏭
Kel: 🤣
Shannon: Hey curious, why pizza?
Kel: Umm
It's just one of my main meals
Shannon: Oh I love that
Kel: Yeah it's pizza come on
Shannon: You ever tried a low cal, high protein HSP?
Kel: Nah I hadn't
I've never had hsp
So the dirty version is chips, cheese, gravy and some sort of meat. Clean version is spud lite, protein cheese and either chicken or beef and then bulked up with salad. It's awesome.
Shannon: Yeah sounds yum
Kel: Done!! 🙌
Shannon: Amazing!!!
How was itM
?*
Kel: The best. I make these quite often. Just usually way more cheese 🤣
Shannon: Massive win!
Well with that high protein cheese you can go nuts!
It's pretty sweet that we can make macro balanced treats hey!
Kel: It's sooooo good!
Shannon: wohooooo!
Shannon: Hey kel! Hows the week treating you? On the shred?
Kel: Hustling 🤣
Shannon: Your hustling?
Kel: Haha trying to get it done.
Work has been busy this week but still hitting the exercise and nutrition.
Shannon: That's awesome to hear!
What's happening at work?
Kel: Just busy. A few things on.
Shannon: Yeah okay!
Can get a little over whelming hey!
How many sessions did you fit in? I can't remember
Last week**
Kel: Everything you set plus a few more. Day off food tracking on Saturday though.
Shannon: Ahh yeah I remember
You went crazy with the hitt as well hey
Was really good!!
Kel: Trying to smash it. Last week I had energy, this week not so much.
Also trying to keep the steps up.
Bulk prepping lunches is a game changer for me as well
Shannon: You don't get sick of eating the same lunches?
Yeah that was a shit ton of workouts, you don't need to push that hard always! Admirable though!
Hows your steps looking each day?
Kel: Nope. Makes it easy and I don't have to think about it.
Shannon: That's good aye
Kel: Steps I try to get 8-10k per day
Shannon: Yeah awesome!
I almost forgot
Kel: I'm averaging about 9k across the week. Gotta love the tracking data
Shannon: We need a pasta meal this week
It's good for motivation hey!
Kel: Was planning on one tonight with chicken
Shannon: High protein pasta + cheese?
Kel: Yeah pretty sure I can fit that in my macros for today. Or the edamame pasta
Shannon: I don't like edamame pasta
Just the vetta pasta
Kel: You don't? I quite like it
Shannon: It's all gloggy
Have you tried the vetta?
Kel: Yeah. I'm using that in my pasta salad. It's great
Shannon: Yeah nice
Which one do you prefer?
Kel: The protein pasta however if I feel like eating a lot with low carbs and cals then the edamame.
Pasta is my weakness!
Shannon: Is the edamame much lower in carbs?
The fav meal?
Kel: Way lower. But also not real pasta 🤣
Yep. Any sort of pasta and lots of it!
Shannon: Surely not
I need to see the macros
Kel: https://slendier.com/product/edamame-bean-spaghetti/
Shannon: Fuck
That's alright hey
It's just the worse pasta though
😂
Kel: What do you have with it?
Shannon: Bolognaise sauce. Sometimes toss some tuna and pesto through it.
That's gains hey
You've got a really good handle on your nutrition
Kel: Except for wine and cheese 🤣
Shannon: Haha
Just hold it to Saturdays though!
Do you drink often?
Kel: Nah not anymore. And never during the week.
Shannon: Easy then!
Drinking sucks for fitness hey, devastating
Fucks your fat loss
Trash hey!
Send me a piccy of your dinner when it's done!
Kel: Boom!
Shannon: Cal count?
Shannon: Crazy
Kel: Morning! After two weeks I'm 2.1kg down and .58 down in body fat. So I'm happy with that!
Shannon: Nice one Kel! Very Proud of your effort! How much more do you have to lose?
Kel: I want to be under 40 for body fat so I'll keep sticking to this. It's pretty easy now thanks to you!
Shannon: I'm glad to hear! Do you rekon the extra support through the week helped witht he motivation?
Kel: Oh for sure. Had to be accountable. So how much for another two weeks?
Shannon: Yeah i like the accountability side of it, having someone chatting to you each week can really help change things, i rekon anyway. So thats what i aim for with clients.
I'm only $19.99/wk + $2 gst, if your keen to keep the momentum going, id love to keep supporting you! No lock in contracts or anything like that.
Kel: Ok let's go for the next two weeks from Monday
It's been brilliant
Let's keep it all the same with the focus on fat loss. So maybe I'll add in more cardio? What do you think?
Shannon: I'm glad your enjoying it! Your doing amazing! Okay yea sounds good to me, how many days of cardio do you want to do? Ill add it into your calendar
https://buy.stripe.com/9AQdTk7rC9XR8Mw9Bn -- Here you go, i managed to skip the gst. This is a subscription, ill cancel it for you in a fortnight :)
Kel: Perfect! I think let's add in a full day of cardio - maybe mid week?
Shannon: Wednesday - sounds good!!
Do you want me to specify the exercises, or do you do your own thing?
Kel: Nah my own thing is fine. I'll smash the elliptical 🤣
Shannon: V nice!
Hands free or what?
Kel: Some times
Shannon: Hands free is def harder
Hahah
Aight hands free this week plz! Might as well make it harder
Kel: Ha sure
Shannon: Just gonna run a class, then I'll adjust your program and let you know!
Kel: Amazing! Have a great Saturday!
Shannon: You too kel! Chat soon!
Shannon: Hey again! I added elliptical into your Wednesday session, I'm going to leave your pull day in there as well, just in case you want to do it. But not necessary!
Anything else I can help with?
Kel: Nah that's all good! Paid all up as well.
Shannon: Yep I saw! Awesome thanks kel! Enjoy your day off today!
Kel: Hey can we swap and make Sunday rest day? I still workout on Saturdays just don't log food.
Shannon: Heya!!
Yeah
Awesome.
I don't actually have you training on Saturdays or Sundays!
I think it's a good idea to just go for a walk on the weekend
How do you feel about that?
Kel: Gym is more of a headspace thing for me. Super important. So I can do lighter on Saturday or make that pure cardio.
Shannon: Yeah okay!
You crazy!
Kel: It works for my head. Keeps the anxiety away.
Shannon: Nah fair fair
I added in epilitical on Saturdays
Kel: Nice thanks
Shannon: Pleasure
You have a good weekend?
Kel: Also just prepped lunch for this week. Chicken Burrito Bowls:
Will add fresh salad each day to them
Yep! Celebrated a friends birthday. You?
Shannon: Killing ittt
Sounds fun!
I just worked in the computer all weekend, little beach walk, few podcasts, was nice!
Kel: ❤
Shannon: Morning 🌄 Ready for a big week?
Kel: Going to smash it
Shannon: Let's gooooooo!
Shannon: Yo hit me! Hows the week been so far?
Kel: Yeah pretty good so far
Shannon: V nice!
Hows the motivation going?
Kel: Oh boy if I relied on motivation I'd be ruined! Routine keeps me going. Gym - food - walking. So all good 🙌
Shannon: Yeah I feel that!!
What do you do to motivate yourself?
Kel: I just know I feel better when I stick to it
Shannon: I see I see
I just crank music super loud
Hows the elliptical going? Hands free?
Kel: Hands free!
It's a killer
Shannon: Haha yeah for sure!
How long you staying on for?
Kel: I did 10mins at the start and end of my workout this morning. Saturday I'll aim for 30mins
Shannon: Yeah awesome
10 minutes is manageable hey!
30 mins is like a mind game
Kel: And tbh I really couldn't be fucked this morning 🤣🤭
Shannon: 😂😂
For sure
Still got it done!
Kel: Then a walking meeting. So my steps are a smashed as well.
Shannon: Really good!
So i was thinking
I wouldn't mind seeing if you could up something thai 🙋
Kel: Thai. I'm not a huge fan.
Shannon: Okay that's fair
Crazy..but fair
🤣
We've done pizza and pasta so far hey
Kel: Yep
Shannon: What about a loaded chips?
Were we talking about this?
Kel: Yes!!! Can totally do that
Spud lite - protein - protein cheese BOOM
Shannon: Bang!
What night you rekon?
Kel: Maybe Sunday
Friday is Pizza night, Saturday I'm out at a gig so yeah Sunday
Shannon: Sunday it is!
Everything else all good? Is your weight moving?
Kel: I'm staying consistent at about 68kg which I'm happy with. Losing fat slowly.
Shannon: Good good!
Hows the food tracking going? I'm about to add a food tracker to my dms so you'll just be able to send photos to me and track your cals that way if that makes things easier for you.
Kel: I use My Fitness Pal and it's pretty good. Scans barcodes, shows remaining macros for the day.
Shannon: Yeah mfp is pretty chill if your used to it!
Cool cool!
It's awesome to see you putting in effort! Thanks for the chat ☺️☺️
Kel: I think for such a long time I was just going through the motions. So it's good to have more structure and see the results. Thank you!
Shannon: Love to be apart of it hey!
❤
Kel: No hands!!
Shannon: Yusss
Good job!!
Shannon: ❤️
Shannon: Big week kel! Ready for it?
Kel: Feeling a bit sluggish tbh
See how the gym goes this morning
Shannon: It's cold ❄️
You got this!!
Shannon: How was leg day?
Kel: Alright… showed up 🤣
Shannon: !!
Big win!
And you got a PB!
Kel: Oh I didn't even realise! I think colder weather combined with wine on the weekend just had me feeling blah. But just smashed a walk so all is back on track!
Shannon: Good to hear!
It was hard today for sure! Glad you got it done!
Shannon: Pretty!
Kel: Running away from the buffet at the conference I'm attending to eat my pre made lunch in the park!
Shannon: That's epic!
Very impressive!!
Shannon: Yo yoooo!
Hows the training been this week?
Kel: Yeah good. Smashed the elliptical this morning - no hands! I've been at a work conference so up extra early to get my training in. Up side it's allowed extra walking 🙌
Shannon: That's really cool to hear!
This is why your work had the buffet lunch yesterday? Is it just in Melbourne?
Kel: Yeah the conference put on food. I had a cheeky chicken slider today 🤭 then a walk. So all good.
Shannon: Yeah awesome!
What's the conference about?
That's really good to be able to say no in situations like that
Kel: Digital Fundraising. Quite interesting.
Oh look, most of the food was rubbish so it wasn't hard.
Shannon: Yeah for sure
Interesting
Fundraising for digital enterprises?
Kel: Mainly for Not for Profits. So I work in disability and we rely on fundraising. But other organisations like Vision Australia and UNICEF were there giving presentations.
Shannon: Okay yeah cool!
What organization do you work for?
Kel: It's called Bayley House. Based in Brighton and also in Hampton East and Highett.
Shannon: Oh nice
We are very close hey!
Kel: Very local!
Shannon: This is looking really good kel!
Kel: I'm certainly feeling incredibly fit. I've increased weights and intensity this week as well
Shannon: Beauty!! On anything particularly?
Weights looking like it's stabalzing at a lower weight as well which is nice
Kel: Most leg exercises I've increased the weight.
Yeah I'm sitting at about 68 comfortably without much effort which I'm happy with.
Shannon: Awesome!
How do you take it to the next level for next week?
Kel: Good question!
What do you suggest?
Shannon: Puts it back on me!
🤣
Make an mad playlist to listen to
Mad*
Kel: Yeah good idea!
Shannon: Nice!
Listen to it when you go for a walk and think about who you want to be
Kel: Any other exercises I could include? Loving the Arnold's and RDLs and the single leg.
TRX I quite like as well, makes me feel really strong
Shannon: I can add some extra exercises into your program!
What you want and where do you want it?
Kel: My Thursday leg day is probably my fave. Absolute killer.
Shannon: Yeah?
Monday might be a good day for lower impact?
Kel: Oh totally. It smashes me. And it's great.
Shannon: Glad to hear it!!
Added some rdls into your Monday to begin with! Theyll be a nice warm up for deadlifts
Kel: Perfect!
Shannon: Some trx rows on pull day?
Kel: Yeah nice
Shannon: Done
And I never saw your loaded tatoes! Sunday night?
😝
Kel: Oh yeah. Wifey made chilli so I had that instead - was too hard to say no 🤭
Will make it this week!
Shannon: Yum!
Easy! No pressure
I'd prefer to see a mad playlist
Kel: Ok sweet, that's easy!
I think the biggest thing for me now is just getting a healthy relationship with all of this. If I easy something off plan it's not big deal. No need to feel guilty. I'm maintaining a consistent weight and not putting on any and I'm feeling fit and strong. So all good I think!
Shannon: Yeah for sure
Consistency is king
Kel: And I love consistency and routine!
Shannon: What the longest exercise/healthy period you've committed to? If that's a valid question?
Same
Kel: Oh this is just how I am. Just sometimes I need a bit more accountability.
I've gone to the gym consistently since I was about 22. But I over ate, smoked, drank a lot. Then about 2 years ago I had a health issue. Turned out I was borderline diabetic and my vitamin d was non existent. So I changed everything. Stopped drinking excessively (I had already stopped smoking) and now I stick to certain calories at least during the week and now that's 6 days per week.
Shannon: Yeah okay
How old are you now?
Kel: 43!
Shannon: Yeah okay
Good on your turning it around!
It's cool a story to hear kel! Glad to be apart of your journey!
Kel: Yeah it's working well!
We will definitely have to catch up soon as well! Too close not to!
Shannon: Yeah for sure
Yus yus!
Anyway! Keep it coming! Umm a meal or a spotify playlist this week! Either or!
Kel: 👍
Kel: Skipped the gym this morning. I've got a cold so went for more sleep instead. Hoping to be feeling better tomorrow and back at it!
Shannon: I love this message!
Yep! Rest when you need to! And get back to it asap! I know you will!
❤
"""  # Ending triple quotes for Kel's log

    print(
        f"\nAttempting to add user '{kel_ig}' and process their dialogue history.")
    process_user_with_dialogue_log(
        kel_ig, kel_sub_id, kel_dialogue_log, kel_bio)
    print(f"\nFinished processing for {kel_ig}.")

    # Optional: Verify Kel's data by uncommenting below
    # print("\nVerifying Kel's conversation history count:")
    # kel_history = get_conversation_history(kel_ig)
    # print(f"Found {len(kel_history)} messages for {kel_ig}.")
    # if kel_history:
    #     print("Last 3 messages for Kel:")
    #     for msg in kel_history[-3:]:
    #         print(f"  [{msg['timestamp']}] ({msg['type']}): {msg['text']}")

    # --- Process Kristy (Dialogue Log) ---
    kristy_ig = "Kristyleecoop"
    kristy_sub_id = "757956347"
    kristy_bio = "Client focused on consistency, strength, and managing workout/life balance."

    kristy_dialogue_log = """\
Shannon: Hey lovely! So sorry no check in video this week! I've been having problems with my computer! But they'll be back next week promise! 🥳🥳
Kristy: Hey no stress whatsoever!
Shannon: Thanks lovely!
Omg it's your birthday today!!
Happy birthday!!!!!
Wohoo
Kristy: Yes it is! Thankyou!
I worked so didn't really feel too birthday like but I had an awesome weekend away with my besties!
Shannon: Okay awesome glad you did!
❤
Get any pressies?
Kristy: Yassss I got spoilt. Got a few tickets to see some bands, new AirPods, some flowers and a new vinyl!
36 is bloody way too close to 40 though
🆘
Shannon: Amazing!!
Oh yeah haha
Oh well 40 is the new 30!
As my dad would say "the only way not to get old is all bad news"
It's a privilege
Kristy: Love it!!
❤
Shannon: Aww you're a gem.
Shannon: Aww you're a gem.
There's something so fun about getting your hands messy and seeing the piece come together.
Looks like it was a blast.
Kristy: Think you msged the wrong person lol
Shannon: woops yeah sorry! 😑
Shannon: woops yeah sorry! 😑
Kristy: 🤣
Shannon: Yo yo! Hows the training been this week
Kristy: Elloooo
I've only trained once 😬 it was a good sesh but I could feel the alcohol from the weekend seeping out of my pores lol
Shannon: Haha oh man, the old alcohol sweat sesh hey! 🤣 Glad you got that one session in though lovely! What did you end up training?
Kristy: It was so bad I felt like a sack of crap 🤣 I did the squat sesh. I ended up going barefoot which helped a lot with stability. No increase in weight but will aim for that next week!
Shannon: Haha yeah, those post-booze sessions are rough!
Barefoot is a good move for stability though.
Keen to see you smash that weight increase next week! 💪 How's the rest of your week looking training-wise?
Kristy: I'm gonna go tomorrow morning and Friday morning. I don't think I'll nail all 4 sessions though because I reaaaaally don't want to train on the weekend. I nailed last week with steps too but this week not so much 🫠
Next week I'll be on
I really don't want to deadlift again this week either… not sure why I'm avoiding it
Shannon: Okay cool, good plan for the next few days!
Don't stress too much about missing sessions or steps, it was your birthday week!
❤
Any idea what's putting you off the deadlifts again this week?
Kristy: I think about doing them and I think "I cannot be fucked" haha
Just being lazy I suppose
Shannon: Haha I hear ya!
That 'cannot be fucked' feeling is real sometimes hey.
Oh well, skip the deadies this week, could just be fatigue from the big week!
Kristy: Yeah cool I will!
Thanks for checking in! You're awesome!
Shannon: My pleasure lovely! Always good chatting. Glad you're finding this helpful! Keep up the good work! Chat soon!
❤
Shannon: My pleasure lovely! Always good chatting. Glad you're finding this helpful! Keep up the good work! Chat soon!
Shannon: Fuck yeah!!
Kristy: 😂😂
Kristy: 😂😂😂😂 that's so true
Honestly it would be torture but because it's her I'm like yassss I wanna hear the cronch
Shannon: 🤣
Kristy: Feels
Kristy: Go me 💁🏻‍♀️
Shannon: Proud of you!
Kristy: Well.. this is a first
Cracked the 15
Shannon: Yooooo
Hahaha
Love it, love the to see the movement throughout the day as well! Really cool!
Kristy: Had to do a few laps of the lounge room to get it at the end of the day lol
Yeah it was an in office days.. they're very different from work from home days lol
Shannon: Really good to see
How are you feeling about it?
Kristy: I'm confused honestly haha. Pre Ozempic I would be in agony from that many steps but now I'm not! I read that it can help with inflammation which is cool. My energy is also so even on this stuff that it's nowhere near as hard to keep up with the movement
It's pretty cool
Shannon: Very cool!!
Movement throughout the day is lit!
Kristy: It's not something that comes easily with a corporate job unfortunately!
Shannon: Definitely, sucks hey
Really proud of your effort! When I log in and see your walks it gets me hyped!
Kristy: Thanks heaps!! Really appreciate the support
Shannon: I'm really glad
Shannon: Hahaha bloody love it
Kristy: 😂
Shannon: Did you deadlift this week!? 😝
Kristy: It's tomorrow! And I'm a bit drunk.. so no? Hahah
I'm at beauty and the beast and I don't wannnnnna deadlift
Shannon: ��😂😂😂😂
Kristy: 😂
I have to break it to you… today is gonna be a very inactive day thanks to last nights red wine 🤣🫣
Oopsie
Shannon: i knew it
Shannon: i knew it
🤣
Kristy: Hahaha this happens sometimes cos I'm a fun time gal
I've got a full day of in office work today AND I'm interviewing people for a position in my team. Pray for me
🤢
Shannon: Fkkkk
Just smoke weed instead of drinking booze seriously
Kristy: No chance
I do not enjoy being stoned
Uppers over downers
Shannon: Alcohol is a downer!
Kristy: Yeah I know but if I was going to stray from alcohol it wouldn't be to a different downer lol
Shannon: Ahhhh oh wrll
Kristy: I don't drink at home or anything just when I go out with friends. Not sure if that makes it better lol
Shannon: Nah that's fair everyone has to enjoy themselves
Kristy: A gals gotta live Shannon
Shannon: A boys gotta lift Kristy
😂
What are you training today? Doing deads? 🤣
Kristy: Nah delts and arms chillllla day
Shannon: Deeee lightful
Enjoy your day lovely! Lots of water and salt!
Kristy: 🫠 dragging myself to 4pm. Have a good one
Kristy: I'm telling myself I'm going to train today
How do people do weekend gym 🫠
Shannon: Music and pre
❤
Let me know once you've had you session plz!
Kristy: I'm here
This is atrocious
Shannon: Hahaha
😂
Come on you got this!
Kristy: Yeah I do now I'm in here lol
Getting here though… 99/100 hard
Shannon: 🤣🤣
Feels
What you Gona train?
Kristy: So my plan is to do both sessions if I have the energy… starting with overhead press and then maybe the deadlift session 🫠
What are you training?
Shannon: Good good!
Rest day for me!! Computer work and beach today!
Kristy: Fuck yeah
Yesms
Going up to 15s for chest press
Feeels good
Anywho I won't keep you on this Saturday! Thanks for the motivation push! Enjoyyyy
Shannon: Thanks for messaging me! I appreciate it!
Get it done! V proud of your effort!
❤
Shannon: Gimme that rascally wabbit
Kristy: 😂😂 she's the best!!
Shannon: Too bloody cute
Kristy: 😊
Kristy: My body is aching 😖😅
Shannon: Another big day!!
Very nice!!
I love the motivation!!
❤
Kristy: I'm trying! 💁🏻‍♀️
Shannon: I can see!!
I feel like you got a good balance right now
Hard work but enjoying yourself!
Kristy: Oh yeah for sure
Gotta have it all ha!!
How's your training going?
Shannon: Interesting hey
It's going good thanks!!
❤
This shred is rough this time honestly struggling to lose weight, but that's all good I'll just keep on keeping on
Training is a bit boring in a weight loss period tbh
Kristy: Yeah that's rough. How much are you trying to lose?
Shannon: Ahhh I dunno maybe 5 more
I have a feeling your messaging me now cuz your going out tomorrow night again? 🤷
Kristy: Jump on the Ozempic you'll be right in 2 weeks 🤣
Shannon: Aahahahahhaa what the hell
Haha send me some
Kristy: I might be
Shannon: M I right???
Kristy: Omg hahahahaha
But that wasn't why I am messaging you now 🤣🤣
Shannon: No but I'm glad you did
😂😂
Kristy: There's a possibility of drinks in the city
Shannon: Nice as! Friends or hubby?
Kristy: But I slept in Monday and didn't train so I need to train Thursday morning so who knows
Friends
Shannon: Nice as!
Yeah skip it n get up early n dominate
Somehow*
What's that shea lebof video
Just do ittttt
Kristy: Isn't that the Nike slogan 🤣
Shannon: It is but he made it his
This is my fave influencer 🤣
Kristy: That's so good hey 😂😂
Shannon: Absolutely cracks me up
I can't believe you don't know the shea leboeuf trip our video
Out*
Kristy: I have never ever heard of it
Also I am certain I am pronouncing his name wrong in my head
Shannon: "Shee-ah La Boof"
Yeah
It's the Terminator kid
He went real weird for a while like 10 years ago
https://youtu.be/ZXsQAXx_ao0?si=0mh-LKtmFCjzIfYE
Hes just so awkward
Kristy: What in the frik is he doing that pose for lol
Shannon: He seems charged
Yeah hahah
He also live streamed himself watching he's own movies for 30 hours 😂😂😂
https://youtu.be/nqihtHPIklc?si=m5pIiiyIMxA70wsL
Kristy: Hahahaha what a nut
Shannon: 🤷
😂
Kristy: Imagine thinking you're that interesting lol
Shannon: Just make sure Thursday morning when you think about not going to the gym
Remember Shea telling you to crush it
Kristy: Hahahhaa
I may instead think of Capacity Joe
Shannon: Nahhhh if I get enough sleep I'll always go
Capacity Joe also a classic
Kristy: Gym makes you feel good though?
Yeah legit. Nothing else helps my mental health quite like it
Eases my OCD symptoms, makes my sleep quality better, makes me so chatty at work lol
Shannon: Yeah awesome
Make sure you get there Thursday then hey!!
Kristy: Ok ok ok okkkkkkkay
So much lecture!
Bed time for me!!
Shannon La Boof
Shannon: Night!
I've reached capacity
😂
Gn
Shannon: Happy easter lovely!
Kristy: You too!!! Hope you are eating mountains of choccy!
Shannon: 😂😂
But the shreds
Faaaaark
Not worth it
🤣🤣🤣
I had a fresh coconut for breaky
Livin that island life
Kristy: Amaze
Did it drop from a tree?
Shannon: Haha it may have… but I bought it from a lovely lady at the market!
Got some celebrations planned today?
Kristy: Amazing!!
Nah just chilling, went for a walk! Now doing some computer work!
Mad chills just how I like it
Shannon: Perfection
Enjoy your island holiday!!!
Kristy: Thankyou! We are off to do a river drift in the Mossman Gorge today. Enjoy your relaxing day… and be kind to yourself and eat some choccy 😅
Shannon: Sounds amazing!!
Shannon: Hows the island lifting going?
Kristy: Absolutely zero lifting out here but I have a win for you
We did this river drift experience and before I went and I had to put my weight in - they cap the weight limit at about 25kg more than I weigh. I was worried they might be like mmmm nah you can't do it. Anyway I felt so good the whole time and in fact it was all the skinny gals with no muscle who struggled to keep up, even getting their boyfriends to carry their rafts through the riverbeds. I feel like all the walking and training in the lead up really really helped me!
Shannon: 💯💯💯💯💯💯
So cool to hear!
Piccies?
Kristy: Have you been to Port Douglas? It's bloody heaven on earth
Shannon: Looks gorgeous!
I haven't no! Where abouts is it?
Kristy: It's far North Queensland. An hour from cairns.
The humidity is fucked - 90-96% everyday so far
Shannon: Ahhh yeah thought it was northern qld
Any Crocs get ya?
Sounds hot af
Kristy: Nearly!!
Shannon: That's long hey
Scary animal
Is this your first time visiting?
Kristy: Bloody oath
I've been to cairns once when I was like 18 but I was a broke kid then
Very different experience
I saw you launched your 100 vid series
Have you got them all filmed already? Huge commitment
Shannon: Oh yeah for sure! But dif when you can pay for the experiences hey
Umm I've done 50, filmed another 25!
I had so many back up vids so it wasn't too hard!
Kristy: Yessss nice one
Absolutely love the passion
Shannon: 😍😍
Your the best!
❤
Kristy: Remember that when you see I've done zero training sessions this week 🙏🏻
Shannon: What else you got planned while your up there?
Kristy: So we did the river float, then we did the croc cruise, then a sunset cruise on a big yacht thing, we did the Kuranda Scenic Rail today and then the sky rail back (omgggg it was fuckin scary) and then tomorrow we are going to the Mossman gorge for a swim and a look around. The room we're in has our own spa and then access directly to the pool from the back gate so we have also been swimming flat out. Fly home on Friday which is awesome cos I wanna see my dog!
What's on for your week? Busy one?
Shannon: Sounds amazing!!
Works so cruisey right now Easter holis!
Class time! You have an awesome rest of your trip! And message me when you get back to it!
Kristy: Sure thing thanks for checking in!
Shannon: Pleasure! Thanks for being an amazing client!
Kristy: That weekly check in video made me cackle
100% down this week
🤣🤣🤣
Shannon: 😂😂😂😂
You improved on several exercises! Bench press 0% 😂
Kristy: 🤣🤣🤣🤣🤣
Nailed it
Shannon: I gotta fix it up a little! 😶‍🌫️
Kristy: Well this weeks improval is gonna be fantastic
Don't know how the eff I'm gonna wake up at 5am tomorrow
Shannon: Amazing! You might win lost improved!
You got this!!
Kristy: 🤣🤣
Shannon: Early bed!
Were you happy to see your doggo?
Kristy: My god it was heaven! She was bucking like a horse and squealing
Shannon: Aww
Kristy: Look how tired she was though
Shannon: Awww
How gooood
Kristy: So good
But back to gym and work tomorrow
rocks back and forth
Shannon: Work 🤢🤢
Book in for the next holiday yet?
Kristy: Hahaha! Well I just found out a good friend of mine got engaged last week and she lives in London. I'm gonna wait to see where/when they plan on getting married and that may actually be the next one!
Shannon: Amazing!!
Are you booking a holiday?
It's always good to plan the next to keep the energy high!!
Kristy: Mhmm none planned! But I was thinking about going home to the goldy today for a week or so!
Shannon: Bloody do it
Get some sun
Better hey!
When winter comes round I rekon
Escape!
Kristy: Yeah good call
Yesms!
I have no events for 4 weeks either
Not even a mid week plan
Shannon: Ohhh she's on
Kristy: I'm gonna go hard at the gym
Shannon: Fuck you have so many plans always
Kristy: lol yeah I do I love it
I'm a social gal
Shannon: Hahaha nice
Gotta live it up
I'm the absolute opposite
Kristy: Whyyyyyy
Gotta live your life
Shannon: I just talk to people all day its nice to just chillax at night ya know
Kristy: Yeah I get that
From 6am cherpy cherpy listener
Shannon: Yep come home and go blank
Yeah podcast time
Kristy: I'm the head of a team of 5
But I dunno
And all day I have question after question… it's nice to completely tune out after work?
!*
I do think it's cool how your always seeing these cool places. Melbourne is sweet for that.
Shannon: Oh yeah I bet!
That would be full on sometimes!
Kristy: My mum was sick for 5 years and my whole life was dedicated to her. When she died I had to relearn how to be my own person with my own life again
It took a while but I am living fully now
Shannon: Oh true
Sorry to hear that!
I'm glad ☺️ gotta send it!
Kristy: Absolutely
Soooooo if I'm learning from my new coach
He has to learn from me
Can I set you a goal?
Shannon: No
😂😂😂
Kristy: Fix my check ins?
I literally rolled my eyes
Shannon: No
Kristy: Once a month try one new experience that doesn't involve fitness
Dare ya!!!
Shannon: No fucking way 💁
Kristy: Bahahahahap
Ok then fix ya fkn check ins
🤣🤣
Shannon: 😂😂😂😂
Hahah
Love it
❤
Shannon: Did you train?
Kristy: Yeah and I hurt my back fml
Fuckk
I took an old steroid tablet I have
And am laying flat working on my laptop 😆
She'll come good tomorrow morn I reckon
Shannon: Ouchie
Fingers crossed
Kristy: I didn't warm up properly before squats and just went for it… my own idiot mistake lol
Anti inflammatories help a lot
Shannon: Oooo
No good
Do you do warm up sets?
Kristy: Yeah I'm chowing down on every tablet in the house lol
I normally do but the gym was full of people this morning and I was overwhelmed and wanted to get it over with 😒
Shannon: Mhmm
Always do your warm up sets plz
Kristy: I'm gettin a tellin off
I was almost not gonna tell ya lol
Shannon: Haha I'm sorry!
Hate hate he tell off
Kristy: Nah you're 100% right though
Yeah
If I'm gonna do it, do it right
Shannon: You just gotta feel it out, take your time, even if you only do squats for that session that's all good ya know. No need to rush it
Kristy: Yeah it's weird I behave like Mr Bean in the gym
I'm an awkward cat
Tried to rush to avoid being surrounded by 18 year old boys 🤣🤣 next time I will try forget other people exist
I gotta show you some photos of how far I've come. I came across comp pics from 2 years ago. The kilos I lost from my body I have also lost from my total tho 😰��
Shannon: Show me!
Yeah don't let people stress you out! Fuck em
They don't even know what's going on
Shannon: Wowsers!!
How much weight loss?
Kristy: Hmmmm bout 30kg
15 on my own and 15 on ozempic
Shannon: Fkkkk
Crazy
Kristy: Haha
Shannon: Perfect 😂
Kristy: I can't even tell you how hard the 15 was on my own
Praise be to lord ozempic 🤣
Shannon: Makes it easier?
Kristy: It's life changing
Shannon: That's interesting hey
Kristy: I just do not give a fuck about food until I'm physically hungry. Previously I was thinking about food all day everyday
Shannon: Yeah true
Constantly starving and searching for dopamine? In food
Kristy: A public shamin' now 🤣🤣
Shannon: Shoulda tagged ya!
😝
Kristy: Bahahaha just here ya go here's a public floggin
This bitch hurt her back!!!!
Shannon: Nah no one will ever know it was you! Plus obviously it's something good to talk about!
Kristy: I might do a video about how PT's need to get their check in videos sorted
Hahahaha
NoT NaMiNg NAmEs
Shannon: Hahaha I'm joking I don't give a fffff
That check in video is a Coco's original thank you v much!
Kristy: Yeah originally with whacked out stats 😆
Shannon: Ain't no body else telling your increase your bench by 0% with low fi hip hop in the background 😝
Kristy: Bahahhahaa
You know it's motivating
I am a loser with a 0% increase and a hurt back
But I am jiving
Shannon: 😮‍💨😮‍💨
But your 30 kilos down!!
Let's goooi
Kristy: 30 to go
This week I'm losing 3
I've decided
Shannon: Jesus
That's a lot!
Kristy: Ozempic and no drinks
I'll aim for 2 and hope for 3
Shannon: No drinks haha love it
You got it!!
❤
I'll chase you up about it!
But I won't pressure to hard!
Kristy: It's gonna happen
Shannon: Let's do it!
Shannon: Have you seen these
Shannon: I've been dying for vegan protein drinks
Kristy: Nah I haven't!!
Shannon: Like a milk?
Kristy: Yeah a milky one in a small like one serve carton I think. I've checked Bentleigh and Moorabbin Woolies and nada
Anywhooooo I'll let you get on with it! Have a good night 🤗
Shannon: Let me know how they goo!
You toooo
Heal up!
❤
Shannon: Yo yoooo! Back at the gym already?
Kristy: Ello
Yup! Back this morn
Backs still a little twingey but fine
Shannon: Awesome!
Glad to hear!
Hows the weight loss going? (It's been 1 day lol)
Kristy: You won't believe this
Stood on the scales this morning
+1.1kg
🤣🤣🤣
Shannon: Beautiful!
Let's see that 3kgss!
Your going to have to send me some of that ozempic
Kristy: Bhahahahahaha
No PLUS 1.1
Fml
Shannon: Ohhhh
Hahahha
Fk
Don't worry about it
A salty dinner can cuz 1-3 kilos tbh
Kristy: I'm not too worried I just chuckled to myself after telling you my aim was 3 ��🤣🤣🤣
Only ate 1,200 cals yesterday or something so I know it's not fat gain
Shannon: Yeah for sure
I'm literally adding half a block of tofu into my daily food to get more protein
Vegan problems
Kristy: For real
Shannon: You can get that
High protein tofu from Cole's have you seen it?
Kristy: Hmmmm nah
That's gotta be a gimmick
Shannon: Coles high protein tofu 17.9g per 100g
Kristy: The organic one I have 15.8g per 90g
Shannon: True
What's the fat comparison?
Kristy: Coles fat 4.6g per 100g
Organic 5.8g per 100g
Shannon: Same same hey
Shannon: Hey
Have you made a pizza for me yet?
Kristy: Hahahha nah
Shannon: Your vegan hey
Kristy: This is my dinner.. you think I'm making anyone anything???
Shannon: Mhmm it's not as good!
Kristy: Yep sure am
Order the butter "chicken" pizza from Greenzilla in st kilda. Best pizza in existence. Do not think of the calorie intake tho
Shannon: Nah terrible calories!
Vegan cheese sucks
Ummm
Kristy: It really does
Shannon: Ummmm
Leave it with me I got class!!
I want to get you to cook a meal
Chat soon xxx
Kristy: lol no
Byeee
Shannon: Vote 1 ubi
Kristy: Socialists then?!
Shannon: Greens forever
I got no idea
I just want a ubi so I can study the universe
Kristy: You can study the universe anyway
We live in the age of information
Shannon: Yeah
But how nice would it be to not have to worry about income
Kristy: It would be amazing but who would do all the sucky jobs if we didn't have to work
Shannon: Robots Kristy robots
Are you excited for the iphone-robot moment?
Kristy: I don't know what that is?! Do tell
Shannon: Remember 1 day no one had iPhones and then literally the next day every single person had an iPhone
That's coming but robots
Kristy: lol ya reckon?
I'm here for it
Shannon: I know
3 - 5 years
Maybe less
Kristy: How do you know?
Shannon: I stay informed
Kristy: Cute tinfoil hat
😂
Shannon: 😂
So many people hate how good tech is getting
Kristy: If it'll make my life easier, bring it on
Shannon: Yeah
It could go wrong but I think it will be good
Kristy: Yeah of course there's risk
I think about elons brain chip that will read our thoughts
Not good for so many reasons but imagine it in someone who's unable to speak or communicate
Life changing shit
Shannon: Yeah
Bloody
Stephen hawkins has these years ago
Plus phones already read our thoughts and give us thoughts
We already brainwashed!
Kristy: lol for sure
Can not wait!
So if we had UBI
You'd still train people wouldn't you?
I've never seen someone who's more committed to their career than you
From what I can see, anyway
Shannon: Aww thanks
Umm
Maybe I don't really know
I'll still have a gym and I'll still hang out with people but my robot can do all the hard work
Kristy: Hahahahaha
Shannon: And my robot can take class when I cbfddd
Kristy: I used to live with a guy who owned a CrossFit and he had an online assistant in the the Phillipines or something that did all his admin
Did all his membership adjustments and payments and general email enquiries
Shannon: Yeah my ex had that
Kristy: Seems like a good investment
I'd quit my job tomorrow if I didn't have to work
Shannon: Take some of the load hey
Not long now seriously
Then it will just be who and what you want to invest your time into
Kristy: Like the Covid lockdown time
You had time to just exist
Try hobbies and live
Shannon: That's was nice
Hard but nice
Kristy: For me, I lost no income so it was nice mostly
Shannon: Yes win
Kristy: Wat a time
Shannon: It was so weird
Kristy: I just drank and ate my way through it
😆
Shannon: 😂😂
The best things hey
Kristy: Well definitely some of my favourite things lol
I could have bathed in this tonight
Why are Asian greens just the fkn best
Shannon: Yum
I've never cooked that up before
Have you ever fried up kale?!
I just bloody love all greens
Kristy: Yeah kale chips
Shannon: Yumo
Kristy: Yessss
Shannon: That's our life soon
Kristy: Hahahahaha
Shannon: 😂😂
Kristy: Caramel protein with some Cinammon sprinkled in might do the trick
Shannon: That's not biscoff!
What's your fav flav?
Kristy: I hate the milky stuff. I have raspberry mojito protein water. Shaken in a cocktail shaker and served on ice 🤣 belissimo
Shannon: 😂😂😂
Fk yeah
Shannon: Helllllo!
Hows your week going?
Kristy: Hiyaaaaa
Busy as hell but good! Have only trained once so far but will make sure I get all 4 in
How are you travelling
Shannon: Yeah you will!
Yeah good! Today I splurged and had a block of choccy and some cookies
So now I'm out going for a walk in this wind 😂
Which sesh did you do?
Kristy: Fuck yeah
I want a cookie
Bench
I'm scared to squat again lol
Shannon: Just do goblet squats
Kristy: Oh god no even worse
Shannon: Hows the progress in the bench?
Don't like goblets?
Kristy: Yeah good. 4x8 at 40kg
Not bad
I did Pilates last night at that new studio in Hampton
I had to stretch my legs apart in the air and whatever that muscle is at the top of your thigh was like a tight rubber band
It was fuuuucked
Shannon: I saw this hahahha
Trying new thingsM
??
Kristy: I've done pilates before. Saw it opened and it's only $4.50 a class for the first two months so why the hell not
I don't stretch so it's gotta do me good
Shannon: Yeah you beauty
It looked pretty groovey
Where is it exactly!?
Kristy: I tell ya what that business model is awesome
Behind the Woolies
There's no instructor. Classes run every hour on the screens. You have an app that unlocks the door to get in
Shannon: Trueeeee
Kristy: You wipe down the equipment so they don't even have anyone in there cleaning
Shannon: That's interesting
Kristy: I reckon they'll go bananas opening up studios now
Shannon: How many people were in there?
Kristy: I'm like fuck yeah I'm quitting my job and opening a pronto 🤣
Shannon: Let's go
Kristy: 10 at a time
Shannon: Future tech
Kristy: The door unlocking by an app was fkn coooool
Yeah
No waiver signing or meeting anyone at all either
Shannon: Hahaha
We love that
Shannon: Did you see this
Shannon: That was Sunday off all days
Kristy: Fuckkk
Big one!
How'd you manage that?
Shannon: I got up early and went to the gym with the intention of doing 10,000 on the treadmill and then going home to rot in bed for the rest of the day but then I ended up going to Southland and then did food shopping and walked Maggie
So I didn't need to go on the treadmilll afterall lol
Win win
Kristy: How good is rotting in bed
Shannon: My favourite activity of all time
Tell me you have good sheets
Kristy: Nah fuck no
Shannon: You need good sheets to rot well
Kristy: My rabbit eats my sheets
Shannon: LOL
what a sentence
🤣🤣🤣🤣🤣
Can't have anything good aye
Kristy: Bunny deserves bed rotting time too
Sacrifices for the greater good
Shannon: It's all worth it
I do appreciate
Nice sheets tho!
What are we talking
Egyptian 1000 thread?
Kristy: https://theladcollective.com/products/tasman-3-0-bedding-set?tw_source=google&tw_adid=729839236757&tw_campaign=22143697394&gad_source=1&gad_campaignid=22143697394&gclid=Cj0KCQjw5ubABhDIARIsAHMighaZgpqB2fwPkf9Rku-0Z-EU3vLJC3I7neAg2ZpXl75n_AD-Tdreq-UaAulAEALw_wcB&variant=43266832203823
These are the only sheets worth having
Shannon: $250
Shannon: Who are you kidding
😂😂
Shannon: 2,920 hours in bed on average a year
Worth it
Kristy: Also note I spend a lot more time in bed than the average person hahhaa
I'm a sloth
Shannon: 😂😂😂
Do the math Shannon
Omg
Cost per use is fantastic
Training time!
Enjoy your sheets!
Byeeeeee
Kristy: She's coming for your sheets
Shannon: Fr fr
Kristy: Me this week 🤦🏻‍♀️
Shannon: 😂😂
Give it time
Kristy: Gaaaaaahhhhhhh
Feels
I'm struggling bad at the moment with being obsessed with self improvement. Well, appearance improvement. It fucks with my head so bad!! This weight obsession lately is killing me. How do you get anywhere without being completely obsessed? You can't! 🫠
Sorry for the vent.. that's a question for my therapist 🤣
Shannon: It's interesting hey
I've been thinking about the same thing lately
I think you do need to be totally obsessed to get things done. And I do think it can play on your mental health for sure. But I dont think it's necessarily a bad thing
Weight loss is fkin hard though hey it's very demanding
Kristy: Yeah you're right
It also makes you obsessed with other aspects.. is my skin good enough? Is my hair nice enough? Do I need veneers? It seems to send me into a self conscious spiral
Absolute insanity lol
Shannon: Mhmm
It's tricky hey
Kristy: So tricky!!?
What do you think about it?
Shannon: I think I consume too much bullshit media and living in a society obsessed with thinness and consumerism has warped my view on reality
I keep trying to squash those thoughts by telling myself to get a grip lol
What do you think about it?
Kristy: Yeah interesting
I think that your environment creates your experience
Shannon: Yeah true
I think it's a good thing to try and be as fit as possible though - but it's better to focus on the process not the outcome
It's weird thing to finally reach your dream body and then watch it slip away, you kind of have to just I dunno learn to enjoy it either way
Kristy: Did you think it was your dream body at the time or was that just in retrospect
Shannon: Mhmm I dunno it's actually kinda weird to talk about
Kristy: Oh yeah sorry!
Shannon: Nah haha I just don't want to sound full of myself 🫢
😂
No I think I achieved whatever I wanted to achieve. And then 3 months later I was 10 kilos heavier and was kind of like well what now
And it just is a bit like well i just need to learn to look at the good parts, and keep pushing and find value in the effort I put in, not what I visually look like
Kristy: Was what you wanted to achieve a look or a feeling? When I was really overweight all I wanted to achieve was to feel comfortable. Now I feel comfortable I want to achieve a look 🙄
Shannon: Umm
It was a look
Kristy: Yeah fair
It's okay to want to look a certain way hey I think.
It's actually crazy how differently people treat you, I spent my whole childhood the chubby kid I could actually feel the difference in the way people treated me when I became fit
Shannon: My god
Shannon: I'm noticing it
Shannon: I think it's a good thing to be fit. And I think it's a good thing to be obsessed but I think it's also hard, emotional, and yeah
❤
Yeah?
Kristy: Yeah I think it's a bloody journey
Yep
Go from a size 22 to a size 14 and people actually see you
Shannon: Yeah for sure I feel that
People didnt even notice me when I was a kid
Kristy: I am a big personality so I feel like I've demanded visibility my whole life on that way cos I didn't get it for any other reason
Shannon: Yeah for sure
You also change as people start to treat you differently
Kristy: I really hope not
Shannon: You change as your environment changes 🙋
Lisa Feldman Barret - your brain uses previous experience to predict what to experience next. Crazy quote
Kristy: Yikes
Is that just a jazzy way to reference hindsight lol
Shannon: In a sense
But it's describes how your brain creates your whole reality, everything you'll every feel, see, hear, experience is based off your previous experience
Pretty deep one
Kristy: Yeah for sure
😝
I need a lobotomy hahaha
Shannon: 😂��😂
Mushrooms 🍄
😂
Shannon: I'm proud of your effort Kristy and feel very special to be a part of it! It's super nice that you reach out to me!
❤
Kristy: You are so great!!
Shannon: ❤
Let's get it! Sunday vibing!
❤
Kristy: Yo! This week has no programming in. Should I just do my 4th sesh from last week tomorrow morning?
Shannon: Ermygawwwd
I'll sought it rn! Any requests?
Kristy: Ummmm
No deadlifts
Anddddd
This thing
Also it's Sunday night so if you cbf please just leave it till tomorrow!
Shannon: Nah I got dis!
Okay so I'm making leg press your big lift for
Legs!
Thatl be a nice change! If you rekon?
Kristy: 🤤
Yep
Shannon: Cool
I'll get something up now, and we can make adjustments through the week if need be!
Kristy: Thanks a mil
Shannon: Thank you
Do you know what this means!
You've been with me for 6 weeks!!!
Kristy: Wow that went quick
Shannon: For sure!
Kristy: My leg muscles know
They are feelin so beefy
Shannon: Fk yeah! 😂
Kristy: It's been so good! I'm excited for the next block
I am scared of how I am gonna be walking tomorrow tho
Shannon: Wohooo!
What day do you want legs?
Kristy: Tuesday plz
Shannon: Okies can do
❤
Kristy: It looks good, thanks!
Shannon: Easy as!!
Shannon: Morning 🌞 ready for a big week!?
Kristy: Ellooo yep I'm training now
Are you?!?
Shannon: Fuckk nice one
Always ready!
Kristy: These reps are different to usual
Ya killin me on bench
Shannon: I'm so outta wack with my shred tbh hahah
What's the reps? 12?.
Kristy: That happens! How do you get back on track?
5 sets of 12
Maybe not the reps, more the sets
Shannon: 2 warm up sets - 3 working sets
Kristy: lol oh
Shannon: I gotta get obsessed, but I'm obsessed with the business rn tbh it's hard to be double obsessed
Sorry I shoulda mentioned
Can't believe your training rn
Kristy: You've only got so much bandwidth
4:50am alarm every training day
Shannon: Crazy crazy
Kristy: Can you can the shred for now
Focus on other shit and get back to it later
"Enjoy your body at all stages" as you said to me on Saturday 😜
Shannon: Nah we double double
But your right I love my body either way
But it's all apart of the business!
Kristy: What do you mean?
Walking, breathing business card?
Shannon: Yup!
Kristy: Fuuuuuck
Well better get your shred in order 🤣
Shannon: Luckily people like a little bit of chub as well
The full story ya know
Kristy: I prefer the relatable
Yeah
Although in saying that who cares lol as long as your product is good ya know
Shannon: Is bunny up
Shannon: We up!
Shannon: Get it girl
Have a good day you two!
❤️❤️
3 working sets for each exercise! I'll adjust if I need just let me know
Kristy: Nah I got it - thanks. One other quick q - if I get into a set and say I get 8 out and I'm cooked would you prefer I do the 8, rest a sec and get the remainder OR should I stop at 8 OR should I stop at 8 and lower the weight for my next set
Shannon: Just do 8! ☺️
❤
Shannon: Chat toooo meeee! What's up in your fitness land?
Kristy: Ello
Have done three days this week. On track to hit 10,000+ everyday this week. Have gone to pilates twice. Went to the doctor and got measured and since Jan have lost 13 around my waist
Shannon: Crazy
Crazy updates hahaha fk
I saw your on some ridiculous sleeping streak
Like 60 days or something!
Kristy: Mate
Its hard for me not to get 8 hours
I have depression don't forget 😂
Shannon: Still good to see
What else is happening? Heading to reformer again this week? Any weight movement on the scales?
Kristy: I am most likely going to Pilates on the weekend! And ZERO weight movement on the scales however I have received like 5 compliments on my weight this week at work lol so must be working
I am going up a dose of the weight loss medication next week so hopefully that kick starts some movement
Shannon: Send me some
😂
Weekend pilates will be a treat
What did you try that was new this week? Or is that a monthly thing?
Kristy: I jogged instead of walked on the treadmill lol!
Which 1/10 do not recommend
Did youuuuuu try anything new
Shannon: Hahaha
Fuckki thattt
Such a gym nerd
Try something!
Omg so this week I had the exact same day as every other day and every night I get overwhelmed with excitement about how amazing it is 😁
Kristy: Ummmm
😳
Shannon: I'm currently building a calorie tracker for my dms - so you can just take a photo and send it through and itl keep it all nice
Kristy: Oooo yeah what program are you using
Shannon: So that's fun
Cursor
Do you know it
Kristy: Nah never heard of it. Is it free?
I'm having a look now
Shannon: It's free
It's coding let me tell ya I've coded up some shit this year
Kristy: Self taught?
I did notice you were using an automatic AI response when we first spoke
Shannon: Fuck off you noticed
Kristy: 100000%
The response was way too quick
Shannon: When?
Ohhh haha
Fixed that a while ago
Yeah self taught, but AI can teach you anything
Kristy: You still signed up hey
Shannon: September
Kristy: Classic
lol
Plz don't use AI to contact me lol
I'd rather no message
Shannon: Fair fair
Don't be upset I don't use AI to talk to you!
Kristy: Sorry but that gave me such an ick
I value real, authentic interactions
Shannon: I get that
You get authentic interactions!
Cool cool
Sorry for upsetting you!
Kristy: Nah no stress all good
Shannon: 😂😂😂
Shannon: You jimmin rn?
Kristy: I slept in 🫠 here now just no time for steps
Too cold
Shannon: It's so cold hey! 3 degrees!
Good effort making it though!
Kristy: Maggie is used to getting up with me at that time for her breakfast so she just kept crying on top of me until I got up so it's not my effort, it's hers lol
Shannon: Awww breakky time will always get you outta bed!
I'm finding if I sleep with clothes on it makes it a little easier to get outta bed in the morning!
Kristy: Oh man lol that is commitment
No leg prisons in bed 👖
Shannon: Hahah
Yeah
Never in summer! But PJs in winter for me I rekon
It's so hard otherwise! Beds so nice in winter hey
Kristy: Yup best place in the world
Safe and warm and has no expectations of uou
Shannon: Haha feels
Saw your vid yesterday
Nice work being vulnerable
Kristy: Oh thanks!
I just think it's an interesting topic
Shannon: Ya I can tell
Our brain is so important in so many ways yet we kinda just forget about it lol
Kristy: Yeah
I dunno I dunno!
I fkin love science
So how's this
You know how I was saying the other day I'm having all these non stop negative thoughts?
Shannon: Depression? Yeah!
Kristy: Nah nah.. like the ones about my appearance… constantly thinking I need to change stuff
Shannon: Oh yeah
The obsession
Kristy: I went to the psych on Thursday and we went through it and she believes that it's my OCD presenting in a different way. Usually it presents as "checking" behaviour which is making sure everything is switched off at home so that I don't burn down the house etc etc… well we have done a bit of work on exposure therapy for that and it's improved the checking behaviours so much… she thinks that my OCD may now be manifesting as repeated negative self thoughts 🙄
Classic
Shannon: Omg bun
So cute
That's interesting
The brain… weird and wonderful
You got dis! You can change your responses with effort!
Kristy: Yeah I know for sure. I've done it once and I can do it again lol
I'm nothing if not persistent!
Bbbby
Shannon: Love watching your journey!
Kristy: I'm increasing the dose of my weight loss injection tonight
Get readdddddy
Shannon: Let's gooo
❤
I Wana try it lol
Kristy: Its so weird
And so good
I'll give you a jab one day lol
Shannon: Why is it weird?
Kristy: Cos overnight so much changes. You do not think about food.. you can eat half of what you usually would.. it does something with inflammation aswell because that all goes away too
Every person I know on it says the same thing
Shannon: It's pretty cool hey
It's like finally there is a drug that actually helps with weight loss
Kristy: Yep which is mind blowing!
I want it to go on the PBS so bad though cos it is so exxy
Shannon: What's the pbs?
Kristy: Public benefit scheme. Most medications are on it and Medicare covers a large portion of the cost of them. If it's not on the PBS it's considered a private medication and you pay the full price
Shannon: Yeah true
It should be cheap hey
Drugs should be affordable
Kristy: My anti depressants are $12 for a month so my previous experience is positive but they haven't added weight loss drugs yet but it would save the country so much money down the track
Shannon: Yeah
Itl come
The durg company's get a certain period where they get to make bank off the drug first or something hey
Kristy: Well I think they'll still make the same money, it's just that the government subsidise it if it's on the PBS
I would like them to foot the bill instead of me lol
Shannon: Training today?
Kristy: Yes chest day!
Shannon: When it gets a little bit warmer
Shannon: You said you only had time for treadmill but I see here you hit 7 personal bests! Not bad!
Kristy: No I said I didnt have time for steps
Only weights
I'd never choose walking over lifting 🤭
Shannon: Oh I see!
Yeah I was thinking that
Perfect!
Kristy: Next block I would like to do less reps and higher weights of bench
12 is so flippin hard
Shannon: Easy as!
Yeah 6 reps only ever
Kristy: lol! Why are you programming me 12 then 🙄🤣
Shannon: 😝😝
I must been feeling mean that day aye
Kristy: Absolutely or it was AI 😬
Shannon: Jeez, ai building workout programs, that would be unheard of
Kristy: Lollllllll
Luckily I need the judgement of a human being to motivate me to go
Shannon: 😂
Kristy: ❤
Shannon: Fair
❤
Shannon: Yooooooi
Hows your week been training wise?
Kristy: Hey only been once but was god
Good
Shannon: Okay yep
You will get the 4 sessions done though hey?
Kristy: I have a dentist appointment tonight so depends on what happens then
If I have to get a tooth pulled, no.
If I don't, yes.
Shannon: Oh no 230
Shannon: Yep fml
Shannon: Had a funeral in Shepparton yesterday and had to leave at 6am… considered a 4am sesh but thought nah I'll go Wednesday.. woke up this morning in agony with the tooth
Anywho I'll give it a shot
Shannon: Dam rough week
Too cold at 430 as well hey
Maybe some weekend sessions?
Kristy: Just couldn't handle a 4am sesh followed by a 3 hour drive lol
Yeah probably have to 🥲
Any other plans for the w/e?
Shannon: Had bottomless brunch plans with some girls from work but that's looking like it's off cos of the weather so will just train, maybe do pilates or something
Or get into bed and scroll for 48 hours 😆
Get some starwars on
I rekon
Kristy: Hellll na
Law and order SVU
Wake up slowly, protein pancakes, then gym, then home
Shannon: Oh boring
Kristy: Nah this new dose has killed my appetite
I had lunch yesterday and had to force it in. Got hungry at 2 today and ate
Eating out of pure necessity at this point lol
Shannon: That's crazy
Kristy: Yep so strange
Shannon: I'm still caught up on you liking law and order
Kristy: It's my favourite show of all time
Don't talk smack about it
👊🏻
Imagine if it wasn't
Kristy: Oi where do you live?
Bentleigh?
Shannon: Oi Bentleigh
We will have to catch up one day! Way too close not to!
Kristy: Yeah for sure!
Maybe we can get some steps in
You can meet this gal
Shannon: That sounds like an awesome plan!
Kristy: For sure
Shannon: Has bunny got a harness?
Shannon: Side note I fuckinnnn broke my 8 hour sleep streak
Kristy: She does but it's not the same
😢
Wtf
???!?!?
Shannon: Monday night
Kristy: I'm filthy about it
Shannon: Cuz the funeral?
Kristy: Yeah I think I was anxious about it or whatever
Then I was fkn itchy, then I was just wired lol
Shannon: Danng
Rough hey
Oh well you'll make it up!
Still that was a good streak
Kristy: I slept from 7pm last night till 6am this morning
😆
Anywho gotta go, dentist time. Thanks for checking in!
Shannon: Good luck!
Kristy: 😂😂😂😂
Shannon: Lehhhh
"""  # Ending triple quotes for Kristy's log

    print(
        f"\nAttempting to add user '{kristy_ig}' and process their dialogue history.")
    process_user_with_dialogue_log(
        kristy_ig, kristy_sub_id, kristy_dialogue_log, kristy_bio)
    print(f"\nFinished processing for {kristy_ig}.")

    # Optional: Verify Kristy's data
    # print("\nVerifying Kristy's conversation history count:")
    # kristy_history = get_conversation_history(kristy_ig)
    # print(f"Found {len(kristy_history)} messages for {kristy_ig}.")
    # if kristy_history:
    #     print("Last 3 messages for Kristy:")
    #     for msg in kristy_history[-3:]:
    #         print(f"  [{msg['timestamp']}] ({msg['type']}): {msg['text']}")
