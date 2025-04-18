#mai.py
from datetime import datetime, timedelta
from langgraph.graph import END, StateGraph
from langchain_core.messages import HumanMessage, AIMessage
from models import (
    Category, ContentType, StateManager, 
    generate_devotion_content, generate_prayer_content, 
    generate_meditation_content, generate_accountability_content,
    get_category_prompt, get_topic_prompt, get_program_length_prompt,
    get_confirmation_prompt, get_calendar_prompt, get_content_type_prompt,
    create_calendar_events, DevotionTopic, PrayerTopic, MeditationTopic,
    AccountabilityTopic, ProgramLength, llm, generate_sos_content,
    NotificationManager
)

# Simplified state transitions
class DSCPLStateMachine:
    def __init__(self):
        self.workflow = StateGraph(state_schema=dict)
        
        # Define nodes
        self.workflow.add_node("initial", self.initial_state)
        self.workflow.add_node("select_category", self.select_category)
        self.workflow.add_node("select_topic", self.select_topic)
        self.workflow.add_node("set_program_length", self.set_program_length)
        self.workflow.add_node("confirm_program", self.confirm_program)
        self.workflow.add_node("deliver_daily_content", self.deliver_daily_content)
        self.workflow.add_node("just_chat", self.just_chat)
        self.workflow.add_node("sos_support", self.sos_support)
        self.workflow.add_node("view_progress", self.view_progress)
        
        # Define edges
        self.workflow.add_edge("initial", "select_category")
        
        self.workflow.add_conditional_edges(
            "select_category",
            self.decide_after_category,
            {
                "just_chat": "just_chat",
                "needs_topic": "select_topic",
                "needs_length": "set_program_length",
                "view_progress": "view_progress",
                "complete": END
            }
        )
        
        self.workflow.add_edge("select_topic", "set_program_length")
        self.workflow.add_edge("set_program_length", "confirm_program")
        
        self.workflow.add_conditional_edges(
            "confirm_program",
            self.decide_after_confirmation,
            {
                "confirmed": "deliver_daily_content",
                "rejected": END
            }
        )
        
        self.workflow.add_edge("deliver_daily_content", END)
        self.workflow.add_edge("just_chat", END)
        self.workflow.add_edge("sos_support", END)
        self.workflow.add_edge("view_progress", END)
        
        self.workflow.set_entry_point("initial")
        self.app = self.workflow.compile()
    
    def is_exit_command(self, text: str) -> bool:
        """Check if the user wants to exit the program"""
        exit_commands = ["exit", "quit", "stop", "end", "bye"]
        return text.lower().strip() in exit_commands

    def handle_exit(self):
        """Handle program exit gracefully"""
        print("\nThank you for using DSCPL. Goodbye!")
        exit(0)

    def initial_state(self, state: dict):
        print("\n" + "="*50)
        print("Welcome to DSCPL - Your Personal Spiritual Assistant")
        print("="*50 + "\n")
        
        session_id = state.get("session_id")
        if not session_id:
            user_id = input("Enter your user ID (or leave blank for guest): ")
            if self.is_exit_command(user_id):
                self.handle_exit()
            user_id = user_id or "guest"
            session_id = StateManager.create_session(user_id)
            state["session_id"] = session_id
            state["user_id"] = user_id
        else:
            session_data = StateManager.get_session(session_id)
            if session_data:
                state.update(session_data)
                
                # Check if we're resuming a program
                if state.get("resume_program"):
                    state["resume_program"] = False
                    
                    # Update the current day based on the start date
                    current_date = datetime.now()
                    start_date = datetime.fromisoformat(state["program_start_date"])
                    
                    # Calculate the current day based on the start date
                    days_passed = (current_date - start_date).days
                    current_day = min(days_passed + 1, state["program_length"])
                    
                    # Update the session with the new current day
                    StateManager.update_session(session_id, {"current_day": current_day})
                    state["current_day"] = current_day
                    
                    print(f"\nResuming program at Day {current_day} of {state['program_length']}")
                    
                    return self.deliver_daily_content(state)
        
        return state
    
    def select_category(self, state: dict):
        print("\n" + "="*50)
        print("What do you need today?")
        print("="*50 + "\n")
        
        while True:
            try:
                choice = input(get_category_prompt())
                if self.is_exit_command(choice):
                    self.handle_exit()
                choice = int(choice)
                if 1 <= choice <= 6:  # Updated to include the Progress option
                    category = list(Category)[choice-1]
                    state["selected_category"] = category.value
                    StateManager.update_session(state["session_id"], {
                        "current_state": "select_category",
                        "selected_category": category.value
                    })
                    StateManager.add_message(state["session_id"], "user", f"Selected category: {category.value}")
                    return state
                print("Invalid choice. Please try again.")
            except ValueError:
                print("Please enter a number between 1-6.")  # Updated range
    
    def decide_after_category(self, state: dict):
        choice = state.get("selected_category")
        if choice == Category.JUST_CHAT.value:
            return "just_chat"
        elif choice == "View Progress":  # Special case for progress dashboard
            return "view_progress"
        return "needs_topic"  # All other categories require topic selection
    
    def select_topic(self, state: dict):
        category = state.get("selected_category")
        if not category:
            print("Error: No category selected")
            return state
        
        print("\n" + "="*50)
        print(f"Select a topic for {category}")
        print("="*50 + "\n")
        
        if category == Category.DEVOTION.value:
            topic_enum = DevotionTopic
        elif category == Category.PRAYER.value:
            topic_enum = PrayerTopic
        elif category == Category.MEDITATION.value:
            topic_enum = MeditationTopic
        elif category == Category.ACCOUNTABILITY.value:
            topic_enum = AccountabilityTopic
        else:
            print("Invalid category for topic selection")
            return state
        
        while True:
            try:
                choice = input(get_topic_prompt(Category(category)))
                if self.is_exit_command(choice):
                    self.handle_exit()
                choice = int(choice)
                if 1 <= choice <= len(topic_enum):
                    topic = list(topic_enum)[choice-1]
                    state["selected_topic"] = topic.value
                    
                    # If it's a devotion, ask for content type preference
                    if category == Category.DEVOTION.value:
                        while True:
                            try:
                                content_choice = input(get_content_type_prompt())
                                if self.is_exit_command(content_choice):
                                    self.handle_exit()
                                content_choice = int(content_choice)
                                if 1 <= content_choice <= len(ContentType):
                                    content_type = list(ContentType)[content_choice-1]
                                    state["content_type"] = content_type.value
                                    break
                                print("Invalid choice. Please try again.")
                            except ValueError:
                                print("Please enter a number.")
                    
                    StateManager.update_session(state["session_id"], {
                        "current_state": "select_topic",
                        "selected_topic": topic.value,
                        "content_type": state.get("content_type")
                    })
                    StateManager.add_message(state["session_id"], "user", f"Selected topic: {topic.value}")
                    return state
                print("Invalid choice. Please try again.")
            except ValueError:
                print("Please enter a number.")
    
    def set_program_length(self, state: dict):
        print("\n" + "="*50)
        print("Program Length Selection")
        print("="*50 + "\n")
        
        while True:
            try:
                choice = input(get_program_length_prompt())
                if self.is_exit_command(choice):
                    self.handle_exit()
                choice = int(choice)
                if 1 <= choice <= len(ProgramLength):
                    length = list(ProgramLength)[choice-1]
                    state["program_length"] = length.value
                    state["current_day"] = 1

                    # Get preferred time from user
                    while True:
                        time_str = input("Enter preferred time (HH:MM) [default: 08:00]: ").strip()
                        if self.is_exit_command(time_str):
                            self.handle_exit()
                        time_str = time_str or "08:00"
                        try:
                            hour, minute = map(int, time_str.split(':'))
                            # Set program start date to next occurrence of requested time
                            now = datetime.now()
                            start_date = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                            if start_date < now:
                                start_date += timedelta(days=1)
                            state["program_start_date"] = start_date.isoformat()
                            break
                        except ValueError:
                            print("Invalid time format. Please use HH:MM (e.g. 08:00 or 13:30)")

                    StateManager.update_session(state["session_id"], {
                        "current_state": "set_program_length",
                        "program_length": length.value,
                        "program_start_date": state["program_start_date"],
                        "current_day": 1
                    })
                    StateManager.add_message(state["session_id"], "user", f"Selected program length: {length.value} {'day' if length.value == 1 else 'days'} at {time_str}")
                    return state
                print("Invalid choice. Please try again.")
            except ValueError:
                print("Please enter a number.")
    
    def confirm_program(self, state: dict):
        print("\n" + "="*50)
        print("Program Overview")
        print("="*50 + "\n")
        
        category = state.get("selected_category")
        topic = state.get("selected_topic")
        length = state.get("program_length")
        
        print(f"By the end of this {length}-{'day' if length == 1 else 'days'} program, you will:")
        
        if category == Category.DEVOTION.value:
            print(f"- Grow in your understanding of {topic} through daily scripture")
        elif category == Category.PRAYER.value:
            print(f"- Deepen your prayer life around {topic}")
        elif category == Category.MEDITATION.value:
            print(f"- Cultivate {topic} through scriptural meditation")
        elif category == Category.ACCOUNTABILITY.value:
            print(f"- Gain strength in overcoming {topic}")
        
        print("\nDaily reminders will be provided to help you stay on track.")
        
        while True:
            response = input(get_confirmation_prompt()).lower()
            if self.is_exit_command(response):
                self.handle_exit()
            if response in ["yes", "y"]:
                state["confirmed"] = True
                StateManager.add_message(state["session_id"], "user", "Confirmed program start")
                
                print("\n" + "="*50)
                print("Generating content for all days...")
                print("="*50 + "\n")
                
                # Generate and store content for each day individually
                for day in range(1, state["program_length"] + 1):
                    print(f"\nGenerating content for Day {day}...")
                    print("-" * 30)
                    
                    if category == Category.DEVOTION.value:
                        content_type = state.get("content_type", ContentType.BOTH.value)
                        # Generate content specifically for this day
                        content = generate_devotion_content(
                            state["selected_topic"],
                            day,  # Pass the specific day number
                            ContentType(content_type)
                        )
                        # Store the content for this specific day
                        StateManager.store_generated_content(
                            state["session_id"],
                            day,
                            "devotion",
                            content
                        )
                        
                    elif category == Category.PRAYER.value:
                        # Generate content specifically for this day
                        content = generate_prayer_content(state["selected_topic"], day)  # Pass the specific day number
                        # Store the content for this specific day
                        StateManager.store_generated_content(
                            state["session_id"],
                            day,
                            "prayer",
                            {"prayer": content}
                        )
                        
                    elif category == Category.MEDITATION.value:
                        # Generate content specifically for this day
                        content = generate_meditation_content(state["selected_topic"], day)  # Pass the specific day number
                        # Store the content for this specific day
                        StateManager.store_generated_content(
                            state["session_id"],
                            day,
                            "meditation",
                            {"meditation": content}
                        )
                        
                    elif category == Category.ACCOUNTABILITY.value:
                        # Generate content specifically for this day
                        content = generate_accountability_content(state["selected_topic"], day)  # Pass the specific day number
                        # Store the content for this specific day
                        StateManager.store_generated_content(
                            state["session_id"],
                            day,
                            "accountability",
                            {"accountability": content}
                        )
                    
                    print(f"Content for Day {day} generated and stored successfully.")
                    print("\n" + "="*50)
                
                # Ask about calendar reminders
                calendar_response = input(get_calendar_prompt()).lower()
                if self.is_exit_command(calendar_response):
                    self.handle_exit()
                if calendar_response in ["yes", "y"]:
                    # Extract time from program start date
                    start_date = datetime.fromisoformat(state["program_start_date"])
                    preferred_time = start_date.strftime("%H:%M")
                    
                    print("\nSetting up Google Calendar integration...")
                    calendar_setup_success = create_calendar_events(
                        state["session_id"],
                        state["program_length"],
                        preferred_time
                    )
                    
                    if calendar_setup_success:
                        print("\n✅ Program successfully added to your Google Calendar")
                        print("You will receive email reminders 1 hour before each session")
                        print("and popup notifications 10 minutes before.")
                    else:
                        print("\nℹ️ Program will continue without calendar integration")
                        print("You can set up calendar reminders later from the settings menu.")
                else:
                    print("\nℹ️ Calendar reminders will not be set up")
                    print("You can set up calendar reminders later from the settings menu.")
                
                # Set up notifications
                try:
                    notification_manager = NotificationManager.get_instance()
                    notification_manager.start()
                    notification_manager.schedule_daily_notifications(
                        state["session_id"],
                        state["program_length"],
                        state["program_start_date"]
                    )
                    print("\n✅ Daily notifications scheduled")
                except Exception as e:
                    print(f"\n⚠️ Could not set up notifications: {e}")
                    print("The program will continue without notifications.")
                
                # Add program to history
                StateManager.add_program_to_history(state["session_id"])
                
                print("\n" + "="*50)
                print("🎉 All content has been generated!")
                print("="*50 + "\n")
                
                return state
            
            elif response in ["no", "n"]:
                state["confirmed"] = False
                StateManager.add_message(state["session_id"], "user", "Declined program start")
                return state
            print("Please answer with 'yes' or 'no'.")
    
    def decide_after_confirmation(self, state: dict):
        return "confirmed" if state.get("confirmed") else "rejected"
    
    def deliver_daily_content(self, state: dict):
        category = state.get("selected_category")
        topic = state.get("selected_topic", "")
        day = state.get("current_day", 1)
        content_type = state.get("content_type", ContentType.BOTH.value)
        
        print("\n" + "="*50)
        print(f"Day {day} of {state['program_length']}")
        print("="*50 + "\n")
        
        # Get content from the database
        content_list = StateManager.get_generated_content(state["session_id"], day)
        
        if not content_list:
            print(f"No content found for Day {day}. Please regenerate the program.")
            return state
        
        content = content_list[0]  # Get the first (and should be only) content for this day
        
        # Display content based on category
        if category == Category.DEVOTION.value:
            if "scripture" in content:
                print("Scripture:\n", content["scripture"])
                print("\nPrayer:\n", content["prayer"])
                print("\nDeclaration:\n", content["declaration"])
            if "video_recommendation" in content and content["video_recommendation"]:
                print("\nVideo Recommendation:", content["video_recommendation"])
            
            message_content = []
            if "scripture" in content:
                message_content.append(f"Scripture:\n{content['scripture']}\n\nPrayer:\n{content['prayer']}")
            if "video_recommendation" in content and content["video_recommendation"]:
                message_content.append(f"Video: {content['video_recommendation']}")
            
            StateManager.add_message(
                state["session_id"],
                "assistant",
                f"Devotion for {topic} (Day {day}):\n" + "\n\n".join(message_content)
            )
        
        elif category == Category.PRAYER.value:
            if "prayer" in content:
                print("\nPrayer Guide:\n", content["prayer"])
                StateManager.add_message(
                    state["session_id"],
                    "assistant",
                    f"Prayer guide for {topic} (Day {day}):\n{content['prayer']}"
                )
        
        elif category == Category.MEDITATION.value:
            if "meditation" in content:
                print("\nMeditation Guide:\n", content["meditation"])
                StateManager.add_message(
                    state["session_id"],
                    "assistant",
                    f"Meditation guide for {topic} (Day {day}):\n{content['meditation']}"
                )
        
        elif category == Category.ACCOUNTABILITY.value:
            if "accountability" in content:
                print("\nAccountability Support:\n", content["accountability"])
                StateManager.add_message(
                    state["session_id"],
                    "assistant",
                    f"Accountability support for {topic} (Day {day}):\n{content['accountability']}"
                )
        
        print("\n" + "="*50)
        
        # Mark the day as completed
        StateManager.mark_day_completed(state["session_id"], day)
        
        # Update the current day in the state
        if day < state["program_length"]:
            state["current_day"] = day + 1
            StateManager.update_session(state["session_id"], {"current_day": day + 1})
        else:
            print("\nCongratulations! You've completed the program.")
            StateManager.add_program_to_history(state["session_id"], completed=True)
        
        return state
    
    def sos_support(self, state: dict):
        """Provide immediate support for users in crisis"""
        topic = state.get("selected_topic", "")
        
        print("\n" + "="*50)
        print("EMERGENCY SUPPORT - You're not alone")
        print("="*50 + "\n")
        
        content = generate_sos_content(topic)
        print(content)
        
        StateManager.add_message(
            state["session_id"],
            "assistant",
            f"Emergency support for {topic}:\n{content}"
        )
        
        print("\n" + "="*50)
        print("Remember: God is with you in this moment.")
        print("Would you like to continue with your program? (yes/no)")
        print("="*50 + "\n")
        
        response = input().lower()
        if response in ["yes", "y"]:
            state["needs_sos"] = False
            return self.deliver_daily_content(state)
        
        return state
    
    def just_chat(self, state: dict):
        print("\n" + "="*50)
        print("Chat Mode - How can I help you today?")
        print("="*50 + "\n")
        print("(Type 'exit' to end the chat)\n")
        
        while True:
            user_input = input("You: ")
            if self.is_exit_command(user_input):
                self.handle_exit()
            
            StateManager.add_message(state["session_id"], "user", user_input)
            history = StateManager.get_conversation_history(state["session_id"])
            
            messages = []
            for msg in history[-6:]:
                if msg["role"] == "user":
                    messages.append(HumanMessage(content=msg["content"]))
                else:
                    messages.append(AIMessage(content=msg["content"]))
            
            messages.append(HumanMessage(content=user_input))
            response = llm.invoke(messages)
            
            print("\nDSCPL:", response.content)
            print()
            StateManager.add_message(state["session_id"], "assistant", str(response.content))
        
        return state

    def view_progress(self, state: dict):
        """Display the user's program history and progress"""
        user_id = state.get("user_id")
        if not user_id:
            print("Error: No user ID found")
            return state
        
        print("\n" + "="*50)
        print("Your Spiritual Journey")
        print("="*50 + "\n")
        
        history = StateManager.get_program_history(user_id)
        
        if not history:
            print("You haven't started any programs yet.")
            print("Start a new program to begin tracking your progress.")
            return state
        
        print("Your Program History:")
        for i, program in enumerate(history, 1):
            status = "✅ Completed" if program["completed"] else "⏸️ Paused" if program["paused"] else "🔄 In Progress"
            print(f"{i}. {program['category']} - {program['topic']} ({program['program_length']} days) - {status}")
        
        print("\nEnter the number of the program to view details, or 'new' to start a new program:")
        choice = input().strip().lower()
        
        if choice == "new":
            return state
        
        try:
            index = int(choice) - 1
            if 0 <= index < len(history):
                program = history[index]
                session_id = program["session_id"]
                
                while True:  # Main loop for viewing program content
                    print("\n" + "="*50)
                    print(f"Program Details: {program['category']} - {program['topic']}")
                    print("="*50 + "\n")
                    
                    progress = StateManager.get_program_progress(session_id)
                    
                    print(f"Total Days: {progress['total_days']}")
                    print(f"Current Day: {progress['current_day']}")
                    print(f"Completed Days: {len(progress['completed_days'])}")
                    print(f"Remaining Days: {len(progress['remaining_days'])}")
                    
                    # Ask user which day's content they want to view
                    while True:
                        try:
                            day_choice = input(f"\nEnter the day number (1-{progress['total_days']}) to view content up to that day, or 'all' to view all days: ").strip().lower()
                            if day_choice == 'all':
                                target_day = progress['total_days']
                                break
                            day_choice = int(day_choice)
                            if 1 <= day_choice <= progress['total_days']:
                                target_day = day_choice
                                break
                            print(f"Please enter a number between 1 and {progress['total_days']}")
                        except ValueError:
                            print("Please enter a valid number or 'all'")
                    
                    # Get stored content from session
                    session_data = StateManager.get_session(session_id)
                    all_content = StateManager.get_generated_content(session_id)
                    
                    if all_content:
                        print(f"\nShowing content for days 1 to {target_day}:")
                        for day_content in all_content:
                            if day_content["day"] <= target_day:
                                print("\n" + "="*50)
                                print(f"Day {day_content['day']} Content:")
                                print("="*50)
                                
                                # Handle different content types
                                if day_content["content_type"] == "devotion":
                                    if "scripture" in day_content:
                                        print("\nScripture:")
                                        print(day_content["scripture"])
                                    if "prayer" in day_content:
                                        print("\nPrayer:")
                                        print(day_content["prayer"])
                                    if "declaration" in day_content:
                                        print("\nDeclaration:")
                                        print(day_content["declaration"])
                                    if "video_recommendation" in day_content:
                                        print("\nVideo Recommendation:")
                                        print(day_content["video_recommendation"])
                                elif day_content["content_type"] == "prayer":
                                    if "prayer" in day_content:
                                        print("\nPrayer Guide:")
                                        print(day_content["prayer"])
                                elif day_content["content_type"] == "meditation":
                                    if "meditation" in day_content:
                                        print("\nMeditation Guide:")
                                        print(day_content["meditation"])
                                elif day_content["content_type"] == "accountability":
                                    if "accountability" in day_content:
                                        print("\nAccountability Support:")
                                        print(day_content["accountability"])
                    else:
                        print("\nNo content available for this program.")
                    
                    print("\nOptions:")
                    print("1. View different day range")
                    print("2. Continue this program")
                    print("3. Start a new program")
                    print("4. Return to main menu")
                    
                    while True:
                        option = input("\nEnter your choice: ").strip()
                        if option in ["1", "2", "3", "4"]:
                            break
                        print("Invalid option. Please enter a number between 1 and 4.")
                    
                    if option == "1":
                        continue  # This will loop back to ask for day choice
                    elif option == "2":
                        # Resume the program
                        state["session_id"] = session_id
                        state["resume_program"] = True
                        
                        # Update the current day in the user_sessions table
                        session_data = StateManager.get_session(session_id)
                        if session_data:
                            # Get the current date
                            current_date = datetime.now()
                            start_date = datetime.fromisoformat(session_data["program_start_date"])
                            
                            # Calculate the current day based on the start date
                            days_passed = (current_date - start_date).days
                            current_day = min(days_passed + 1, session_data["program_length"])
                            
                            # Update the session with the new current day
                            StateManager.update_session(session_id, {"current_day": current_day})
                            state["current_day"] = current_day
                            
                            print(f"\nResuming program at Day {current_day} of {session_data['program_length']}")
                        
                        return state
                    elif option == "3":
                        # Start a new program
                        return state
                    elif option == "4":
                        # Return to main menu
                        return state
        except ValueError:
            print("Invalid choice. Returning to main menu.")
        
        return state

# Main execution
def main():
    print("Initializing DSCPL AI Agent...")
    state_machine = DSCPLStateMachine()
    state = {}
    
    # Start notification system
    notification_manager = NotificationManager.get_instance()
    notification_manager.start()
    
    try:
        # First run - show welcome message
        result = state_machine.app.invoke(state)
        if not result.get("session_id"):
            return
        state = {"session_id": result["session_id"], "user_id": result.get("user_id")}
        
        # Continue running without showing welcome message again
        while True:
            # Skip the initial state if we're continuing a program
            if state.get("resume_program"):
                state["resume_program"] = False
                result = state_machine.deliver_daily_content(state)
            else:
                result = state_machine.app.invoke(state)
                
            if not result.get("session_id"):
                break
                
            state = result
            
            # After delivering content, ask if user wants to continue
            if result.get("current_state") == "deliver_daily_content":
                print("\n" + "="*50)
                print("Would you like to continue with your program?")
                print("="*50 + "\n")
                print("Press Enter to continue or type 'exit' to end: ")
                
                user_input = input().strip().lower()
                if user_input == "exit":
                    print("\nThank you for using DSCPL. Goodbye!")
                    break
    except KeyboardInterrupt:
        print("\nGoodbye! May God bless your day.")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        # Stop notification system
        notification_manager.stop()

if __name__ == "__main__":
    main()