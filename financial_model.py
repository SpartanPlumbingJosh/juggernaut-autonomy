"""
Financial model projecting monthly revenue growth from $0 to $12M ARR over 5 years.
Calculates required MRR growth rates, churn assumptions, and customer acquisition needs.
Outputs monthly targets in cents aligned with deadline 2031-01-01.
"""

from datetime import datetime, timedelta
import math

def calculate_growth_plan(
    target_arr: float = 12_000_000,  # $12M ARR target
    target_date: str = "2031-01-01",
    starting_mrr: float = 0,
    starting_customers: int = 0,
    avg_customer_mrr: float = 100,  # $100/month average
    starting_churn_rate: float = 0.05,  # 5% monthly churn
    min_churn_rate: float = 0.01,  # 1% monthly churn floor
    churn_improvement: float = 0.95,  # 5% improvement in churn each year
) -> list[dict]:
    """
    Calculate monthly growth plan to reach target ARR by deadline.
    Returns list of monthly targets with:
    - month (YYYY-MM)
    - mrr_cents (monthly recurring revenue in cents)
    - new_customers (customers added that month)
    - churn_rate (monthly churn rate)
    - total_customers
    """
    target_date = datetime.strptime(target_date, "%Y-%m-%d").date()
    current_date = datetime.now().date()
    
    # Calculate number of months until target
    months = (target_date.year - current_date.year) * 12 + (target_date.month - current_date.month)
    if months <= 0:
        raise ValueError("Target date must be in the future")
    
    # Calculate required monthly growth rate using compound growth formula
    required_growth_rate = math.pow(target_arr / (starting_mrr * 12), 1/months) - 1
    
    # Initialize variables
    results = []
    current_mrr = starting_mrr
    current_customers = starting_customers
    current_churn = starting_churn_rate
    
    for month in range(months):
        # Calculate date for this month
        year = current_date.year + (current_date.month + month - 1) // 12
        month_num = (current_date.month + month - 1) % 12 + 1
        month_str = f"{year}-{month_num:02d}"
        
        # Calculate churn for this month (improving over time)
        if month > 0 and month % 12 == 0:
            current_churn = max(min_churn_rate, current_churn * churn_improvement)
        
        # Calculate MRR target for this month
        target_mrr = starting_mrr * math.pow(1 + required_growth_rate, month + 1)
        
        # Calculate required new customers accounting for churn
        churned_customers = current_customers * current_churn
        required_customers = target_mrr / avg_customer_mrr
        new_customers = max(0, required_customers - (current_customers - churned_customers))
        
        # Update current values
        current_customers = current_customers - churned_customers + new_customers
        current_mrr = current_customers * avg_customer_mrr
        
        results.append({
            "month": month_str,
            "mrr_cents": round(current_mrr * 100),  # Convert to cents
            "new_customers": round(new_customers),
            "churn_rate": current_churn,
            "total_customers": round(current_customers),
        })
    
    return results

def print_growth_plan(plan: list[dict]):
    """Print formatted growth plan table"""
    print(f"{'Month':<8} {'MRR ($)':>12} {'New Customers':>15} {'Churn Rate':>12} {'Total Customers':>15}")
    print("-" * 70)
    for month in plan:
        print(
            f"{month['month']:<8} "
            f"${month['mrr_cents']/100:>11,.2f} "
            f"{month['new_customers']:>15,} "
            f"{month['churn_rate']:>12.2%} "
            f"{month['total_customers']:>15,}"
        )

if __name__ == "__main__":
    plan = calculate_growth_plan()
    print_growth_plan(plan)
