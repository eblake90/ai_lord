import os
import subprocess
import tempfile
import asyncio
import py_compile
from openai import OpenAI
from dotenv import load_dotenv

# ---------------------------
# Configuration and Parameterisation
# ---------------------------
CONFIG = {
    "model": "gpt-4o",
    "temperature": 0.7,
    "max_review_iterations": 3,
    "api_timeout": 10  # seconds for subprocess.run timeout
}

# Load environment variables from the .env file.
load_dotenv()

# Initialise the OpenAI client using the API key.
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
if not client.api_key:
    raise ValueError("OPENAI_API_KEY not found in environment variables.")

# ---------------------------
# Global Conversation Log for Stateful Context
# ---------------------------
conversation_log = []


# ---------------------------
# LangGraph Node Infrastructure with Real-Time Logging
# ---------------------------
class Node:
    def __init__(self, name, function=None):
        """
        :param name: A descriptive name for the node.
        :param function: A callable that processes input data.
        """
        self.name = name
        self.function = function
        self.next_node = None

    def set_next(self, node):
        """Connect this node to the next node in the pipeline."""
        self.next_node = node

    def process(self, data):
        """Process data through this node, printing the input and output in real time."""
        print(f"[{self.name}] Received input: {data}")
        result = self.function(data) if self.function else data
        print(f"[{self.name}] Produced output: {result}")
        if self.next_node:
            return self.next_node.process(result)
        return result


# ---------------------------
# LLM Functions for Manager, Coder, Feedback, Judge, and Reporter Nodes
# ---------------------------
def manager_function(request):
    """
    Calls the Manager LLM to outline the plan.
    """
    try:
        response = client.chat.completions.create(
            model=CONFIG["model"],
            messages=[
                {"role": "system",
                 "content": (
                     "You are a manager. Your sole responsibility is to outline a detailed plan listing "
                     "all the tasks and steps required to achieve the input request. DO NOT produce any code. "
                     "Only provide a clear and concise plan."
                 )},
                {"role": "user", "content": request}
            ],
            temperature=CONFIG["temperature"]
        )
        outline = response.choices[0].message.content.strip()
        return outline
    except Exception as e:
        return f"An error occurred in manager_function: {e}"


def coder_function(plan, extra_instruction=""):
    """
    Calls the Coder LLM to generate Python code based on the plan and optional extra instructions.
    Saves the code and executes it.
    Returns a dictionary with the code and its execution output.
    """
    try:
        prompt = (
            f"Here is the plan:\n\n{plan}\n\n"
            "Please produce only the Python code implementation for the above plan. "
            "Ensure that the code is plain Python (do not include markdown formatting such as triple backticks) "
            "and that it compiles without syntax errors."
        )
        if extra_instruction:
            prompt += f"\n\nAdditionally, incorporate the following instruction into your code: {extra_instruction}"

        response = client.chat.completions.create(
            model=CONFIG["model"],
            messages=[
                {"role": "system",
                 "content": (
                     "You are a coder. Based on the provided plan, generate only the Python code implementation. "
                     "Do not include any markdown formatting. Output plain Python code only. "
                     "Ensure the code compiles without syntax errors."
                 )},
                {"role": "user", "content": prompt}
            ],
            temperature=CONFIG["temperature"]
        )
        code_text = response.choices[0].message.content.strip()

        # Save the generated code
        output_directory = "./output"
        os.makedirs(output_directory, exist_ok=True)
        script_path = os.path.join(output_directory, "solution.py")
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(code_text)

        # Automatic Syntax Check
        syntax_error = ""
        try:
            py_compile.compile(script_path, doraise=True)
        except py_compile.PyCompileError as e:
            syntax_error = f"Syntax error detected: {e}"

        # Execute the script
        try:
            result = subprocess.run(
                ["python", script_path],
                capture_output=True,
                text=True,
                timeout=CONFIG["api_timeout"]
            )
            execution_output = result.stdout + "\n" + result.stderr
        except Exception as e:
            execution_output = f"Error running code: {e}"

        # If a syntax error was detected, prepend it to the execution output
        if syntax_error:
            execution_output = syntax_error + "\n" + execution_output

        return {"code": code_text, "output": execution_output}
    except Exception as e:
        return {"code": "", "output": f"An error occurred in coder_function: {e}"}


def bojack_horseman_function(data):
    """
    Calls bojack_horseman to provide purely critical feedback on functional aspects of the code and its output.
    Emphasize syntax errors if present.
    """
    code_text = data["code"]
    execution_output = data["output"]
    try:
        response = client.chat.completions.create(
            model=CONFIG["model"],
            messages=[
                {"role": "system",
                 "content": (
                     "You are bojack_horseman. Your job is to evaluate the provided Python code and its execution output, "
                     "focusing solely on the functional implementation and output quality. "
                     "If there is a syntax or compilation error, highlight it as the most critical issue. "
                     "Point out design flaws, logical errors, inefficiencies, and any other critical issues. "
                     "Do not mention any positive aspects. If no significant issues are found, state that succinctly."
                 )},
                {"role": "user",
                 "content": (
                     f"Please critique the following Python script and its execution output:\n\n"
                     f"--- CODE ---\n{code_text}\n\n"
                     f"--- EXECUTION OUTPUT ---\n{execution_output}\n\n"
                     "Provide a detailed, purely critical evaluation, prioritizing any syntax or compilation errors."
                 )}
            ],
            temperature=CONFIG["temperature"]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"An error occurred in bojack_horseman_function: {e}"


def mr_peanut_butter_function(data):
    """
    Calls mr_peanut_butter to provide purely positive feedback on functional aspects of the code and its output.
    """
    code_text = data["code"]
    execution_output = data["output"]
    try:
        response = client.chat.completions.create(
            model=CONFIG["model"],
            messages=[
                {"role": "system",
                 "content": (
                     "You are mr_peanut_butter. Your job is to evaluate the provided Python code and its execution output, "
                     "focusing solely on the functional implementation and output quality. "
                     "Highlight effective design choices, robust implementation, and well-executed output that demonstrate the code’s ability to fulfill its intended purpose. "
                     "Do not mention any negative aspects. If no significant positive features are found, state that succinctly."
                 )},
                {"role": "user",
                 "content": (
                     f"Please praise the following Python script and its execution output:\n\n"
                     f"--- CODE ---\n{code_text}\n\n"
                     f"--- EXECUTION OUTPUT ---\n{execution_output}\n\n"
                     "Provide a detailed, purely positive evaluation."
                 )}
            ],
            temperature=CONFIG["temperature"]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"An error occurred in mr_peanut_butter_function: {e}"


async def async_feedback_branch(data):
    """
    Asynchronously calls both bojack_horseman_function and mr_peanut_butter_function concurrently.
    Returns a dictionary with both critical and positive feedback.
    """
    loop = asyncio.get_event_loop()
    bojack_future = loop.run_in_executor(None, bojack_horseman_function, data)
    mr_peanut_future = loop.run_in_executor(None, mr_peanut_butter_function, data)
    negative_feedback, positive_feedback = await asyncio.gather(bojack_future, mr_peanut_future)
    return {"negative_feedback": negative_feedback, "positive_feedback": positive_feedback}


def save_feedback_function(feedback):
    """
    Saves the feedback from bojack_horseman and mr_peanut_butter into separate files.
    """
    output_directory = "./output"
    os.makedirs(output_directory, exist_ok=True)
    bojack_file = os.path.join(output_directory, "bojack_horseman.txt")
    mr_peanut_file = os.path.join(output_directory, "mr_peanut_butter.txt")
    try:
        with open(bojack_file, "w", encoding="utf-8") as f:
            f.write(feedback.get("negative_feedback", ""))
        with open(mr_peanut_file, "w", encoding="utf-8") as f:
            f.write(feedback.get("positive_feedback", ""))
        return f"Feedback saved successfully: {bojack_file}, {mr_peanut_file}"
    except Exception as e:
        return f"An error occurred while saving feedback: {e}"


def judge_function(manager_outline, coder_result, feedback, review_count, conversation_history):
    """
    Calls the Judge LLM to evaluate whether the script meets the Manager's outline.
    Incorporates conversation history for stateful context.
    Prioritize syntax errors if detected.
    """
    try:
        judge_prompt = (
            f"Manager's Outline:\n{manager_outline}\n\n"
            f"Python Code:\n{coder_result['code']}\n\n"
            f"Execution Output:\n{coder_result['output']}\n\n"
            f"Feedback from bojack_horseman (critical):\n{feedback['negative_feedback']}\n\n"
            f"Feedback from mr_peanut_butter (positive):\n{feedback['positive_feedback']}\n\n"
            "Based on the above, determine whether the script achieves the Manager's outline. "
            "If a syntax or compilation error is present, prioritize this as the main issue that must be fixed immediately. "
            "If the script meets the outline, provide a brief summary and state that the goal has been achieved. "
            "If not, provide clear instructions for the coder to modify the code. "
            "Do not invent issues or strengths beyond what is provided."
        )
        if conversation_history:
            judge_prompt += "\n\nConversation History:\n" + "\n".join(conversation_history)
        if review_count >= CONFIG["max_review_iterations"]:
            judge_prompt += (
                "\nThis is your final review. End the process by providing a final summary, "
                "regardless of whether the script fully meets the outline or not."
            )
        response = client.chat.completions.create(
            model=CONFIG["model"],
            messages=[
                {"role": "system",
                 "content": (
                     "You are the Judge. Your job is to review the Manager's outline, the Python code, its execution output, "
                     "and the feedback from bojack_horseman and mr_peanut_butter. Determine whether the script meets the Manager's outline. "
                     "If it does, provide a concise summary and state that the goal has been achieved. "
                     "If it does not, provide clear instructions for the coder to modify the code, prioritizing any syntax errors. "
                     "Focus strictly on whether the functional goals have been met."
                 )},
                {"role": "user", "content": judge_prompt}
            ],
            temperature=CONFIG["temperature"]
        )
        judge_response = response.choices[0].message.content.strip()
        achieved = "achieved" in judge_response.lower() or "final summary" in judge_response.lower()
        return {"achieved": achieved, "instruction": judge_response}
    except Exception as e:
        return {"achieved": False, "instruction": f"An error occurred in judge_function: {e}"}


def reporter_function(conversation_log):
    """
    Calls the Reporter LLM to produce a detailed and illustrated report of the conversation between all LLMs.
    The report should include bullet points summarizing each exchange, similar to:

    - **Manager to Coder**: Manager provided a detailed outline for a task involving generating and visualizing a positively skewed distribution.
    - **Coder to Bojack/Mr_Peanut (Iteration 1)**: Coder shared the generated code and its execution output for feedback.
    - **Bojack_Horseman/Mr_Peanut (Iteration 1)**: Provided critical and positive feedback on the Coder's initial output.
    - **Judge to Coder (Iteration 1)**: Judge acknowledged the script's effectiveness but pointed out a runtime error, suggesting a solution.
    - **Coder to Bojack/Mr_Peanut (Iteration 2)**: Coder submitted revised code after addressing Judge's feedback.
    - **Bojack_Horseman/Mr_Peanut (Iteration 2)**: Offered further feedback on the revised code.
    - **Judge to Coder (Iteration 2)**: Judge confirmed the script now meets the outline, and the task is complete.
    - **Judge**: Declared the task completed successfully, ending the pipeline.

    The report is saved to 'report.txt'.
    """
    try:
        # Instruct Reporter with a detailed sample format
        report_instructions = (
            "Please produce a detailed report summarizing the conversation between all LLMs in the following format:\n\n"
            "- **Manager to Coder**: Manager provided a detailed outline for a task involving generating and visualizing a positively skewed distribution.\n"
            "- **Coder to Bojack/Mr_Peanut (Iteration 1)**: Coder shared the generated code and its execution output for feedback.\n"
            "- **Bojack_Horseman/Mr_Peanut (Iteration 1)**: Provided critical and positive feedback on the Coder's initial output.\n"
            "- **Judge to Coder (Iteration 1)**: Judge acknowledged the script's effectiveness but pointed out a runtime error, suggesting a solution.\n"
            "- **Coder to Bojack/Mr_Peanut (Iteration 2)**: Coder submitted the revised code and execution output after addressing Judge's feedback.\n"
            "- **Bojack_Horseman/Mr_Peanut (Iteration 2)**: Offered further critical and positive feedback on the revised code.\n"
            "- **Judge to Coder (Iteration 2)**: Judge confirmed the script now fully meets the Manager's outline, with improvements and no critical errors.\n"
            "- **Judge**: Declared the task completed successfully, achieving the goal set out by the Manager, and ended the pipeline.\n\n"
            "Now, using the following conversation log, produce a bullet-point summary of the conversation:"
        )
        report_prompt = report_instructions + "\n\n" + "\n".join(conversation_log)
        response = client.chat.completions.create(
            model=CONFIG["model"],
            messages=[
                {"role": "system",
                 "content": (
                     "You are Reporter. Your task is to produce a detailed and illustrated report summarizing the conversation between all LLMs. "
                     "Follow the sample format provided exactly, including bullet points that describe who spoke to whom, why, and what was communicated."
                 )},
                {"role": "user", "content": report_prompt}
            ],
            temperature=CONFIG["temperature"]
        )
        report_text = response.choices[0].message.content.strip()

        # Save the report to a .txt file
        report_path = os.path.join("./output", "report.txt")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_text)
        return f"Report saved successfully to {report_path}\n\nReport:\n{report_text}"
    except Exception as e:
        return f"An error occurred in reporter_function: {e}"


# ---------------------------
# Main Pipeline Execution with Judge Loop (Asynchronous Main)
# ---------------------------
async def main():
    user_request = input("Enter your request: ")

    # Manager LLM produces the outline
    manager_outline = manager_function(user_request)
    print("\nManager's Outline:\n", manager_outline)
    conversation_log.append("**Manager to Coder**: Manager provided the detailed outline for the task.")

    review_count = 1
    achieved = False
    extra_instruction = ""

    while review_count <= CONFIG["max_review_iterations"] and not achieved:
        print(f"\n=== Judge Review Iteration {review_count} ===")
        # Coder LLM generates or updates the code using the plan and any extra instruction from the Judge
        coder_result = coder_function(manager_outline, extra_instruction)
        print("\nCoder's Code:\n", coder_result["code"])
        print("\nCoder's Execution Output:\n", coder_result["output"])
        conversation_log.append(
            f"**Coder to Bojack/Mr_Peanut (Iteration {review_count})**: Coder generated the code and execution output.")

        # Generate feedback asynchronously from bojack_horseman and mr_peanut_butter concurrently
        feedback = await async_feedback_branch(coder_result)
        print("\nFeedback from bojack_horseman:\n", feedback["negative_feedback"])
        print("\nFeedback from mr_peanut_butter:\n", feedback["positive_feedback"])
        conversation_log.append(
            f"**Bojack_Horseman/Mr_Peanut (Iteration {review_count})**: Provided critical and positive feedback on the coder's output.")

        # Save the feedback to files
        save_feedback_function(feedback)

        # Judge reviews everything including conversation history
        judge_decision = judge_function(manager_outline, coder_result, feedback, review_count, conversation_log)
        print("\nJudge's Decision:\n", judge_decision["instruction"])
        conversation_log.append(f"**Judge to Coder (Iteration {review_count})**: {judge_decision['instruction']}")

        if judge_decision["achieved"]:
            achieved = True
            final_summary = judge_decision["instruction"]
            print("\nFinal Summary and Decision by Judge:\n", final_summary)
            conversation_log.append(
                "**Judge**: Declared the task completed successfully, achieving the goal set out by the Manager, and ended the pipeline.")
            break
        else:
            extra_instruction = judge_decision["instruction"]
            review_count += 1

    if not achieved:
        print("\nJudge's final review completed. The pipeline is terminating with the current version of the script.")
        conversation_log.append(
            "**Judge**: Final review completed. Pipeline terminates without fully meeting the goal.")

    # Reporter LLM produces a summary report of the conversation
    report_result = reporter_function(conversation_log)
    print("\nReporter Output:\n", report_result)


if __name__ == "__main__":
    asyncio.run(main())
