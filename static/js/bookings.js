

async function advanceBooking() {
    let bookingDate = document.getElementById("bookingDate").value;
    let checkinTime = document.getElementById("checkinTime").value;
    let checkoutTime = document.getElementById("checkoutTime").value;
    let cardNumber = document.getElementById("cardNumber").value;
    let expiryDate = document.getElementById("expiryDate").value;
    let cvv = document.getElementById("cvv").value;

    if (!bookingDate || !checkinTime || !checkoutTime || !cardNumber || !expiryDate || !cvv) {
        alert("Please fill all fields before proceeding.");
        return;
    }

    try {
        // ✅ Step 1: Get the smallest available slot from Flask
        let slotResponse = await fetch("/get_smallest_available_slot");
        let slotData = await slotResponse.json();

        if (!slotData.smallest_slot) {
            alert("No available slots. Try again later.");
            return;
        }

        let smallestSlot = slotData.smallest_slot;
        console.log("Auto-selected Slot:", smallestSlot);  // Debugging log

        // ✅ Step 2: Send Booking Data to Flask
        let bookingData = {
            slot_number: smallestSlot,  // Auto-selected slot
            booking_date: bookingDate,
            checkin_time: checkinTime,
            checkout_time: checkoutTime,
            payment_status: "paid"
        };

        console.log("Sending booking data:", bookingData);  // Debugging log

        let response = await fetch("/save_advance_booking", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(bookingData)
        });

        let result = await response.json();
        console.log("Response received:", result);  // Debugging log

        if (result.status === "success") {
            alert("Booking confirmed! Slot: " + smallestSlot);
            window.location.href = "/my_bookings";
        } else {
            alert("Error: " + result.message);
        }
    } catch (error) {
        console.error("Error:", error);
    }
}
