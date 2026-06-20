from agents.manager.manager import manager_agent
from agents.developer.developer import developer_agent
from agents.reviewer.reviewer import reviewer_agent

from storage import save_log


def run_system(user_input: str):

    print("\n🧠 MANAGER PROCESSING...\n")

    plan = manager_agent(user_input)

    print(plan)

    save_log(
        stage="manager",
        input_text=user_input,
        output_text=plan
    )


    print("\n💻 DEVELOPER WORKING...\n")

    dev_output = developer_agent(plan)

    print(dev_output)

    save_log(
        stage="developer",
        input_text=plan,
        output_text=dev_output
    )


    print("\n🔍 REVIEWER ANALYZING...\n")

    review = reviewer_agent(dev_output)

    print(review)

    save_log(
        stage="reviewer",
        input_text=dev_output,
        output_text=review
    )


    print("\n✅ FINAL OUTPUT COMPLETE\n")

    save_log(
        stage="system",
        input_text=user_input,
        output_text=review
    )


if __name__ == "__main__":

    while True:

        user_input = input("\nYou: ")

        if user_input.lower() in ["exit", "quit"]:
            break

        run_system(user_input)