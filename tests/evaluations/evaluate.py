import json
import time
import logging
import sys
from agent.agent import run_agent

# --- SET UP CLEAN FILE LOGGING ---
logger = logging.getLogger("EVALUATOR")
logger.setLevel(logging.INFO)

# Clear any existing console handlers from your default logger
if logger.hasHandlers():
    logger.handlers.clear()

# Route all logs to a file instead of the console
file_handler = logging.FileHandler("logs\\benchmark_run.log", encoding="utf-8")
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)
# ---------------------------------

def load_dataset(filepath: str):
    with open(filepath, 'r', encoding='utf-8') as file:
        return json.load(file)

def run_evaluation(dataset_path: str):
    dataset = load_dataset(dataset_path)
    
    total_questions = len(dataset)
    successful_executions = 0
    exact_data_matches = 0
    total_time = 0.0
    total_in_tokens = 0.0
    total_out_tokens = 0.0
    
    print(f"🚀 Starting evaluation on {total_questions} questions...")
    print("Writing detailed logs to 'logs/benchmark_run.log'...\n")
    
    for i, item in enumerate(dataset, 1):
        # Print a clean, single-line progress update to the console
        sys.stdout.write(f"\rTesting question {i}/{total_questions} [{item['id']}]...")
        sys.stdout.flush()
        
        logger.info(f"--- Testing [{item['id']} - {item['difficulty'].upper()}]: {item['question']} ---")
        if i > 1:
            time.sleep(7)  # Add a delay between questions to manage rate limits
        start_time = time.perf_counter()
        
        try:
            state_result = run_agent(item["question"])

            #cost calculation---------------------------
            input_tokens = state_result.get("input_tokens", 0)
            output_tokens = state_result.get("output_tokens", 0)
            total_in_tokens += input_tokens 
            total_out_tokens += output_tokens
            logger.info(f"💸 Cost of this query:{(input_tokens*(0.05/1000000)) + (output_tokens*(0.08/1000000)):.6f} USD (Input tokens: {input_tokens}, Output tokens: {output_tokens})")
            #--------------------------------------------
            
            if state_result.get("error") is None and state_result.get("result") is not None:
                successful_executions += 1
                
                raw_result = state_result["result"]
                normalized_agent_data = [
                    [str(col) if col is not None else None for col in row] 
                    for row in raw_result
                ]
                
                agent_data_str = sorted(normalized_agent_data)
                expected_data_str = sorted(item["expected_data"])
                
                if agent_data_str == expected_data_str:
                    exact_data_matches += 1
                    logger.info("✅ PASS: Data matches perfectly.")
                else:
                    logger.warning("❌ FAIL (Data Mismatch):")
                    logger.warning(f"Expected: {expected_data_str}")
                    logger.warning(f"Got:      {agent_data_str}")
                    logger.warning(f"Agent SQL: {state_result.get('generated_sql')}")
            else:
                logger.error(f"❌ FAIL (Execution Error): {state_result.get('error')}")

        except Exception as e:
            logger.error(f"❌ CRITICAL CRASH: {str(e)}")
            
        elapsed = time.perf_counter() - start_time
        logger.info(f"⏱️ Time taken: {elapsed:.2f} seconds\n")
        total_time += elapsed

    # Print Final Benchmark Report to Console
    print("\n\n" + "=" * 50)
    print("📊 EVALUATION BENCHMARK REPORT")
    print("=" * 50)
    print(f"Total Questions Tested: {total_questions}")
    print(f"Execution Success Rate: {(successful_executions / total_questions) * 100:.1f}%")
    print(f"Data Match Accuracy:    {(exact_data_matches / total_questions) * 100:.1f}%")
    print(f"Average Latency:        {(total_time / total_questions):.2f} seconds/query")
    print(f"Total Evaluation Time:  {total_time:.2f} seconds")
    print(f"Total evaluation cost: ${(total_in_tokens*0.05/1000000) + (total_out_tokens*0.08/1000000):.6f}")
    print("=" * 50 + "\n")
    print("Detailed failure logs saved to 'logs/benchmark_run.log'")

if __name__ == "__main__":
    run_evaluation("evals\golden_dataset.json")